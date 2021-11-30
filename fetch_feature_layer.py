"""
Fetch a feature layer from an arcgis server and write/update it to a PostGIS database.

references:
- https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer-.htm
- https://support.esri.com/en/technical-article/000019645
"""
import urllib.parse
import urllib.request
import json
from datetime import datetime
import fire
from sqlalchemy import Table, MetaData, Column, Integer, Float, Text, TIMESTAMP, create_engine
from sqlalchemy.sql import select
from geoalchemy2.types import Geometry
from shapely.geometry import shape
from shapely.geometry.multipolygon import MultiPolygon
from shapely.geometry.polygon import Polygon
from shapely import wkb


def get_column_type(value):
    """ Return the correct sqlalchemy column type for a given value. """
    if isinstance(value, int):
        return Integer()
    if isinstance(value, float):
        return Float()
    if isinstance(value, str):
        return Text()
    raise Exception(f'unknown type {type(value)}')


def create_table_schema(meta_data: MetaData, data: dict, table_name: str, geom_type: str,
                        srid: int) -> Table:
    """
    Create a table schema.
    geom_type: geometry type (e.g. POLYGON or MULTIPOLYGON)
    srid: spatial reference id (e.g. 4326)
    """
    columns = {}
    for feature in data['features']:
        for key, value in feature['properties'].items():
            if not key in columns:
                columns[key] = Column(key.lower(), get_column_type(value))

    return Table(table_name, meta_data,
                 Column('id', Integer(), primary_key=True, nullable=False),
                 Column('geom', Geometry(geometry_type=geom_type, srid=srid, spatial_index=True,
                        from_text='ST_GeomFromEWKT', name='geometry'), nullable=False),
                 Column('create_date', TIMESTAMP(
                     timezone=True), nullable=False),
                 Column('update_date', TIMESTAMP(
                     timezone=True), nullable=False),
                 *list(columns.values()),
                 schema=None)


def fetch_object_list(url: str):
    """
    Fetch object list from a feature layer.

    url: layer url to fetch (e.g. https://maps.gov.bc.ca/arcserver/rest/services/whse/bcgw_pub_whse_legal_admin_boundaries/MapServer/2)
    """
    print(f'fetching object list for {url}...')

    params = {
        'where': '1=1',
        'geometryType': 'esriGeometryEnvelope',
        'spatialRel': 'esriSpatialRelIntersects',
        # 'outSR': '102100',
        # 'outFields': '*',
        'returnGeometry': 'false',
        'returnIdsOnly': 'true',
        'f': 'json'
    }

    encode_params = urllib.parse.urlencode(params).encode("utf-8")
    print(f'{url}/query?{encode_params.decode()}')
    with urllib.request.urlopen(f'{url}/query?', encode_params) as response:
        json_data = json.loads(response.read())
    return json_data['objectIds']


def fetch_object(object_id: int, url: str):
    """
    Fetch a single object from a feature layer. We have to fetch objects one by one, because they
    can get pretty big. Big enough, that if you ask for more than one at a time, you're likely to
    encounter 500 errors.

    object_id: object id to fetch (e.g. 1)
    url: layer url to fetch (e.g. https://maps.gov.bc.ca/arcserver/rest/services/whse/bcgw_pub_whse_legal_admin_boundaries/MapServer/2)
    """
    print(f'fetching object {object_id}')

    params = {
        'where': f'objectid={object_id}',
        'geometryType': 'esriGeometryEnvelope',
        'spatialRel': 'esriSpatialRelIntersects',
        # 'outSR': '102100',
        'outFields': '*',
        'returnGeometry': 'true',
        'returnIdsOnly': 'false',
        'f': 'geojson'
    }

    encode_params = urllib.parse.urlencode(params).encode("utf-8")
    print(f'{url}/query?{encode_params.decode()}')
    with urllib.request.urlopen(f'{url}/query?', encode_params) as response:
        json_data = json.loads(response.read())
    return json_data


def sync_layer(url: str, host: str, dbname: str, user: str, password: str, table: str,
               geom_type: str = 'MULTIPOLYGON', srid: int = 4326, port: int = 5432):
    """
    Sync a feature layer.

    url: layer url to sync (e.g. https://maps.gov.bc.ca/arcserver/rest/services/whse/bcgw_pub_whse_legal_admin_boundaries/MapServer/2)
    host: database host (e.g. localhost)
    dbname: database name (e.g. tileserver)
    user: database user (e.g. tileserver)
    password: database password (e.g. tileserver)
    table: table name (e.g. my_fancy_table)
    geom_type: e.g. POLYGON or MULTIPOLYGON
    srid: e.g. 4326
    """
    print(f'syncing {url}...')

    meta_data = MetaData()
    db_string = f'postgresql://{user}:{password}@{host}:{port}/{dbname}'
    engine = create_engine(db_string, connect_args={
                           'options': '-c timezone=utc'})
    table_schema = None

    with engine.connect() as connection:

        ids = fetch_object_list(url)
        for object_id in ids:
            obj = fetch_object(object_id, url)

            if table_schema is None:
                # We base our table off the first object we get back.
                table_schema = create_table_schema(
                    meta_data, obj, table, geom_type, srid)

            if not engine.dialect.has_table(connection, table):
                meta_data.create_all(engine)

            for feature in obj['features']:
                geom = shape(feature['geometry'])

                # If we're expecting multipolygons, we need to convert the polygon to a
                # multipolygon.
                if geom_type == 'MULTIPOLYGON' and isinstance(geom, Polygon):
                    geom = MultiPolygon([geom])

                wkt = wkb.dumps(geom, hex=True, srid=srid)
                props = {key.lower(): value for key,
                         value in feature['properties'].items()}
                values = {'id': feature['id'], 'geom': wkt, **props}

                rows = connection.execute(select(table_schema).where(
                    table_schema.c.id == feature['id']))
                exists = False
                for row in rows:
                    if row:
                        exists = True
                    break

                values['update_date'] = datetime.now()
                if exists:
                    print('record exists, updating')
                    connection.execute(table_schema.update().where(
                        table_schema.c.id == feature['id']).values(values))
                else:
                    print('create new record')
                    values['create_date'] = values['update_date']
                    connection.execute(table_schema.insert().values(values))


if __name__ == '__main__':
    fire.Fire(sync_layer)

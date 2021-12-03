from urllib.parse import quote_plus as urlquote
from datetime import datetime
import fire
from sqlalchemy import Table, MetaData, Column, Integer, Float, Text, TIMESTAMP, create_engine, func
from sqlalchemy.ext.automap import automap_base
from geoalchemy2.types import Geometry


def generate_custom(host: str, dbname: str, user: str, password: str, fire_zone_label_table: str,
                    fire_centre_table: str, port: int = 5432, srid: int = 4326):
    meta_data = MetaData()
    db_string = f'postgresql://{user}:{urlquote(password)}@{host}:{port}/{dbname}'
    engine = create_engine(db_string, connect_args={
                           'options': '-c timezone=utc'})

    Base = automap_base()
    Base.prepare(engine, reflect=True)

    FireZonesLabels = Base.classes[fire_zone_label_table]
    FireCentres = Base.classes[fire_centre_table]

    columns = [Column('id', Integer(), primary_key=True, nullable=False),
               Column('geom', Geometry(geometry_type="POINT", srid=srid, spatial_index=True,
                                       from_text='ST_GeomFromEWKT', name='geometry'), nullable=False),
               Column('create_date', TIMESTAMP(
                   timezone=True), nullable=False),
               Column('update_date', TIMESTAMP(
                   timezone=True), nullable=False)]
    exclude_zone = ('geom', 'id', 'update_date', 'create_date')
    exclude_centre = ('geom', 'id', 'update_date', 'create_date')
    for column in FireZonesLabels.__table__.columns:
        if column.name not in exclude_zone:
            columns.append(Column(f'fire_zone_{column.name}', column.type,
                                  primary_key=column.primary_key, nullable=column.nullable))
    for column in FireCentres.__table__.columns:
        if column.name not in exclude_centre:
            columns.append(Column(f'fire_centre_{column.name}', column.type,
                                  primary_key=column.primary_key, nullable=column.nullable))

    new_table = Table('fire_zones_labels_ext',
                      meta_data, *columns, schema=None)

    with engine.connect() as connection:
        if not engine.dialect.has_table(connection, new_table):
            new_table.create(engine)

        # iterate through fire zones
        for fire_zone in connection.execute(FireZonesLabels.__table__.select()):
            # iterate through fire centres
            # print(fire_zone)
            for fire_centre in connection.execute(FireCentres.__table__.select(func.ST_Within(
                    fire_zone.geom, FireCentres.geom))):
                values = {}
                for key, value in fire_zone._mapping.items():
                    if key not in exclude_zone:
                        values[f'fire_zone_{key}'] = value
                for key, value in fire_centre._mapping.items():
                    if key not in exclude_centre:
                        values[f'fire_centre_{key}'] = value
                values['geom'] = fire_zone.geom
                values['update_date'] = datetime.now()
                values['create_date'] = values['update_date']
                connection.execute(new_table.insert().values(values))
                break

    # new_table = Table('fire_zones_labels_ext', meta_data,
    #                   *FireZonesLabels.__table__.columns,
    #                   schema=None)


if __name__ == '__main__':
    fire.Fire(generate_custom)

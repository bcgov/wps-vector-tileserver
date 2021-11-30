# Taken from:
# https://support.esri.com/en/technical-article/000019645
# Minus the token stuff

# referenced https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer-.htm


import urllib.parse
import urllib.request
import os
import json
import tempfile
import fire
import subprocess


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
    response = urllib.request.urlopen(f'{url}/query?', encode_params)
    json_data = json.loads(response.read())
    return json_data['objectIds']


def fetch_object(object_id: int, url: str):
    """
    Fetch a single object from a feature layer. We have to fetch objects one by one, because they can get pretty big. Big enough,
    that if you ask for more than one at a time, you're likely to encounter 500 errors.

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
    response = urllib.request.urlopen(f'{url}/query?', encode_params)
    json_data = json.loads(response.read())
    return json_data

def sync_layer(url: str, host: str, dbname: str, user: str, password: str, table: str):
    """
    Sync a feature layer.

    url: layer url to sync (e.g. https://maps.gov.bc.ca/arcserver/rest/services/whse/bcgw_pub_whse_legal_admin_boundaries/MapServer/2)
    host: database host (e.g. localhost)
    dbname: database name (e.g. tileserver)
    user: database user (e.g. tileserver)
    password: database password (e.g. tileserver)
    table: table name (e.g. my_fancy_table)
    """
    print(f'syncing {url}...')

    ids = fetch_object_list(url)
    for id in ids:
        obj = fetch_object(id, url)
        with tempfile.TemporaryDirectory() as temporary_path:
            filename = os.path.join(os.getcwd(), temporary_path, f'obj_{id}.json')
            with open(filename, "w") as f:
                json.dump(obj, f)
            # NOTE: There's an issue with 453 (that's the Fraser Fire Zone) - it's being served up as a multipolygon which happens
            # to also contain Haida Gwaii. All other features are polygons, so the table as greated with a polygon geom column. When
            # this feature is encountered, it fails because it can't squeeze a multipolygon into a polygon.
            command = f'ogr2ogr -f "PostgreSQL" PG:"dbname={dbname} host={host} user={user} password={password}" "{filename}" -nln {table}'
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
            process.wait()
            print(f'process exited with code {process.returncode}')
            os.remove(filename)

if __name__ == '__main__':
    fire.Fire(sync_layer)

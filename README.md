# wps-tileserver
Vector tile server for the Wildfire Predictive Services Unit 
## Get the data

### Fire Zones

https://maps.gov.bc.ca/arcserver/rest/services/whse/bcgw_pub_whse_legal_admin_boundaries/MapServer/8

https://maps.gov.bc.ca/arcserver/rest/services/whse/bcgw_pub_whse_legal_admin_boundaries/MapServer/8/query?where=objectid%3=1000&f=json

see: scripts/fetch_feature_layer.py

```

```

## Put date in DB

## Configure pg_tile server

Docker sucks when it needs to connect to localhost - so:

```bash
mkdir pg_tileserv
cd pg_tileserv
wget https://postgisftw.s3.amazonaws.com/pg_tileserv_latest_linux.zip
unzip pg_tileserv
export DATABASE_URL=postgresql://wps:wps@localhost/wps
./pg_tileserv
```

## Serve up data

## Review process to keep data up to date


## Idea
Easily spin up a vector tile server that will syncronize with some source.

### Components
0. postgis (external).
1. pg_tileserv - serves up vector tiles from postgis server.
2. proxy server (varnish?) - caches responses.
3. sync cronjob - updates database periodically.
## Reference
https://blog.crunchydata.com/blog/production-postgis-vector-tiles-caching

## Assumptions
- You have the oc command line installed and you're logged in.
- You have docker installed locally.
- You have a postgres database in your target openshift environment that can be accessed by pg_tileserv
## Instructions

```bash
# we have docker limits, so pull the images local - then put them in openshift

# pull local
docker pull eeacms/varnish
docker pull pramsey/pg_tileserv

# tag for upload
docker tag eeacms/varnish image-registry.apps.silver.devops.gov.bc.ca/e1e498-tools/varnish:latest
docker tag pramsey/pg_tileserv image-registry.apps.silver.devops.gov.bc.ca/e1e498-tools/pg_tileserv:latest

# log in to openshift docker
docker login -u developer -p $(oc whoami -t) image-registry.apps.silver.devops.gov.bc.ca

# push it
docker push image-registry.apps.silver.devops.gov.bc.ca/e1e498-tools/varnish:latest
docker push image-registry.apps.silver.devops.gov.bc.ca/e1e498-tools/pg_tileserv:latest

# deploy pg_tileserv
oc -n e1e498-dev process -f tileserv.yaml | oc -n e1e498-dev apply -f -
```
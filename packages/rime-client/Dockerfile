FROM nginx:alpine

ENV STA_ENDPOINT=""
ENV STA_VERSION="v1.1"

# Render templates into the webroot instead of the default /etc/nginx/conf.d.
# nginx.conf itself needs no templating; rime-client serves static files only.
ENV NGINX_ENVSUBST_OUTPUT_DIR=/usr/share/nginx/html/js

COPY packages/rime-client/nginx.conf /etc/nginx/conf.d/default.conf
COPY packages/rime-client/runtime-config.js.template /etc/nginx/templates/
COPY web/rime /usr/share/nginx/html

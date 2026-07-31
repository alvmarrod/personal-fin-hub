#!/bin/sh
echo "  Frontend nginx running on http://0.0.0.0:80"
exec nginx -g "daemon off;"

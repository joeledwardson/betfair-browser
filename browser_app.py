"""
heroku app script
"""
import os
from mybrowser.browser import get_app

DATABASE_URL = os.environ['DATABASE_URL']

# see stack question - have to edit postgres string:
# https://stackoverflow.com/questions/62688256/sqlalchemy-exc-nosuchmoduleerror-cant-load-plugin-sqlalchemy-dialectspostgre
start = 'postgres://'
if not DATABASE_URL.startswith(start):
    raise Exception(f'expected database URL to start with "{start}", instead got "{DATABASE_URL}"')
url = DATABASE_URL.replace(start, 'postgresql://')

# set url to database url and schema
schema = 'bettingschema'
config = {
    'DB_CONFIG': {
        'engine_kwargs': {
            'url': url,
            'connect_args': {
                'options': f'-c search_path={schema},public'
            }
        }
    }
}

app = get_app(additional_config=config)

# set server variable to be read by heroku
server = app.server

# turn of dev tools prop check to disable time input error
app.run_server(debug=False, dev_tools_props_check=False, use_reloader=False, host='0.0.0.0')

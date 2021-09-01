from mybrowser.browser import get_app
import logging
logging. basicConfig(level=logging.WARNING)

app = get_app()
server = app.server
# turn of dev tools prop check to disable time input error
app.run_server(debug=False, dev_tools_props_check=False, use_reloader=False)



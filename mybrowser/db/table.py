from ..config import config
from myutils.myregistrar import MyRegistrar
from datetime import date, datetime


formatters = MyRegistrar()


@formatters.register_element
def format_datetime(dt: datetime):
    return dt.strftime(config['TABLE']['dt_format'])


def table_out(tbl_cols, db, max_rows, id_col, fmt_config):

    q_final = db.session.query(*tbl_cols).limit(max_rows)
    q_result = q_final.all()
    tbl_rows = [dict(r) for r in q_result]
    for i, row in enumerate(tbl_rows):

        # set 'id' column value to betfair id so that dash will set 'row-id' within 'active_cell' correspondingly
        row['id'] = row[id_col]

        # apply custom formatting to table row values
        for k, v in row.items():
            if k in fmt_config:
                nm = fmt_config[k]
                f = formatters[nm]
                row[k] = f(v)

    return tbl_rows

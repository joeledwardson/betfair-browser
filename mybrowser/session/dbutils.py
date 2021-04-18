from sqlalchemy.sql.functions import sum as sql_sum


def runner_rows(db, market_id, strategy_id):
    """
    get filters rows of runners, joined with profit column from strategy
    """
    sr = db.tables['strategyrunners']
    cte_strat = db.session.query(
        sr.columns['runner_id'],
        sr.columns['profit'].label('runner_profit')
    ).filter(
        sr.columns['strategy_id'] == strategy_id,
        sr.columns['market_id'] == market_id
    ).cte()

    rn = db.tables['marketrunners']
    return db.session.query(
        rn,
        cte_strat.c['runner_profit'],
    ).join(
        cte_strat,
        rn.columns['runner_id'] == cte_strat.c['runner_id'],
        isouter=True,
    ).filter(
        rn.columns['market_id'] == market_id
    ).all()


def market_meta(db, market_id):
    """
    get meta information about a market
    """
    return db.session.query(
        db.tables['marketmeta']
    ).filter(
        db.tables['marketmeta'].columns['market_id'] == market_id
    ).first()


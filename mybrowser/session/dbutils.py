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

    rn = db.tables['runners']
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


def q_strategy(strategy_id, db):
    """
    get query for marketmeta , filtered to markets for strategy specified with additional "market_profit" column for
    total profit for strategy for given market, grouped over runner profits per market

    Parameters
    ----------
    strategy_id :

    Returns
    -------
    """
    sr = db.tables['strategyrunners']
    meta = db.tables['marketmeta']

    strat_cte = db.session.query(
        sr.columns['market_id'],
        sql_sum(sr.columns['profit']).label('market_profit')
    ).filter(
        sr.columns['strategy_id'] == strategy_id
    ).group_by(
        sr.columns['market_id']
    ).cte()

    return db.session.query(
        meta,
        strat_cte.c['market_profit']
    ).join(
        strat_cte,
        meta.columns['market_id'] == strat_cte.c['market_id']
    )
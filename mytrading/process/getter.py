"""
Use True to return dictionary getter, False to return attribute getter

betfairlightweight RunnerBookEx ojects available_to_back, available_to_lay, traded_volume are inconsistent in
appearing as lists of dicts with 'price' and 'size', and lists of PriceSize objects.
"""
GETTER = {
    True: dict.get,
    False: getattr
}
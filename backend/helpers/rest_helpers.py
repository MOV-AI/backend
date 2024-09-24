from aiohttp import web


def deprecate_endpoint() -> None:
    """This is a helper function to deprecate unused functions

    Raises:
        web.HTTPForbidden
    """
    raise web.HTTPForbidden(reason="This endpoint is deprecated")


def fetch_request_params(request: dict) -> dict:
    """fetches the params from the request and returns them in a dictionary.

    Args:
        request (dict): The request with the params.

    Returns:
        dict: A dictionary of params and their value.
    """
    params = {}
    if request.query_string != "":
        if "&" in request.query_string:
            for param in request.query_string.split("&"):
                name, value = param.split("=")
                params[name] = value
        else:
            name, value = request.query_string.split("=")
            params[name] = value
    return params

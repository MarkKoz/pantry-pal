from typing import NamedTuple
from unittest.mock import create_autospec
from urllib.parse import urlencode

import flask
import pytest
from werkzeug import exceptions

from tests import SPOONACULAR_KEY
from web.api import SPOONACULAR_BASE


class Endpoint(NamedTuple):
    name: str
    spoonacular: str
    method: str
    limit: int


ENDPOINTS = (
    Endpoint("api.search_api", "recipes/complexSearch", "GET", 2),
    Endpoint("api.ingredient_api", "food/ingredients/autocomplete", "GET", 50),
)


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_endpoints_success(client, requests_mock, endpoint):
    """On success, Spoonacular's response should be forwarded with a 200 status code."""
    data = dict(hello="world")
    requests_mock.request(endpoint.method, SPOONACULAR_BASE + endpoint.spoonacular, json=data)

    res = client.open(flask.url_for(endpoint.name), method=endpoint.method)

    assert res.status_code == 200
    assert res.get_json() == data


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_api_key_passed(client, requests_mock, endpoint):
    """Spoonacular API key should be passed as a query parameter to the Spoonacular request."""
    requests_mock.request(endpoint.method, SPOONACULAR_BASE + endpoint.spoonacular, json={})

    client.open(flask.url_for(endpoint.name), method=endpoint.method)

    # qs is generated by urllib.parse.parse_qs, which puts values in lists.
    assert requests_mock.last_request.qs == dict(apiKey=[SPOONACULAR_KEY])


@pytest.mark.parametrize("endpoint", [e for e in ENDPOINTS if e.method == "GET"])
def test_get_params_forwarded(client, requests_mock, endpoint):
    """Query parameters should be forwarded to the Spoonacular request."""
    requests_mock.get(SPOONACULAR_BASE + endpoint.spoonacular, json={})

    client.get(flask.url_for(endpoint.name, hello="world"))

    # Remove the apiKey because it is independently tested elsewhere.
    qs = requests_mock.last_request.qs
    qs.pop("apiKey", None)

    # qs is generated by urllib.parse.parse_qs, which puts values in lists.
    assert qs == dict(hello=["world"])


@pytest.mark.parametrize("endpoint", [e for e in ENDPOINTS if e.method == "POST"])
def test_post_data_forwarded(client, requests_mock, endpoint):
    """Data should be forwarded to the Spoonacular request as x-www-form-urlencoded."""
    data = dict(hello="world")
    requests_mock.post(SPOONACULAR_BASE + endpoint.spoonacular, json={})

    client.post(flask.url_for(endpoint.name), data=data)

    # data is encoded as application/x-www-form-urlencoded
    assert requests_mock.last_request.text == urlencode(tuple(data.items()), doseq=True)


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_spoonacular_error_forwarded(client, requests_mock, endpoint):
    """Response and status code should be forwarded from Spoonacular upon failure."""
    data = dict(
        status="failure",
        code=401,
        message="You are not authorized. Please read ...",
    )
    requests_mock.request(
        endpoint.method,
        SPOONACULAR_BASE + endpoint.spoonacular,
        json=data,
        status_code=data["code"],
        headers={"content-type": "application/json"},
    )

    res = client.open(flask.url_for(endpoint.name), method=endpoint.method)

    assert res.status_code == data["code"]
    assert res.get_json() == data


@pytest.mark.parametrize("endpoint", ENDPOINTS)
@pytest.mark.parametrize("error", [exceptions.BadRequest(), exceptions.InternalServerError()])
def test_error_json_response(client, endpoint, error):
    """Errors should return responses in JSON."""
    client.application.view_functions[endpoint.name] = create_autospec(
        client.application.view_functions[endpoint.name], spec_set=True, side_effect=error
    )

    res = client.open(flask.url_for(endpoint.name), method=endpoint.method)

    assert res.status_code == error.code
    assert res.get_json() == dict(
        status="failure",
        code=error.code,
        message=f"{error.name}: {error.description}",
    )


@pytest.mark.parametrize("param", ["addRecipeNutrition"])
@pytest.mark.parametrize(["value", "expected_status"], [("true", 403), ("false", 200)])
def test_search_disabled_params(client, requests_mock, param, value, expected_status):
    """Search endpoint should return 403 when disabled params are true, and 200 when false."""
    requests_mock.get(SPOONACULAR_BASE + "recipes/complexSearch", json={})

    res = client.get(flask.url_for("api.search_api", **{param: value}))

    assert res.status_code == expected_status


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_rate_limits(client, requests_mock, endpoint):
    """Endpoints should be rate limited."""
    requests_mock.request(endpoint.method, SPOONACULAR_BASE + endpoint.spoonacular, json={})

    for _ in range(endpoint.limit):
        # A new context is needed to clear flask.g cause flask-limiter stores state in there.
        with client.application.app_context():
            res = client.open(flask.url_for(endpoint.name), method=endpoint.method)
            assert res.status_code == 200

    res = client.open(flask.url_for(endpoint.name), method=endpoint.method)
    assert res.status_code == 429
    assert res.headers["Retry-After"] == "120"

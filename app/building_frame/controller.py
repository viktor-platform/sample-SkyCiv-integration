import json

from munch import Munch
from skyciv.lib.request import request

from viktor import UserError
from viktor.core import ViktorController
from viktor.core import progress_message
from viktor.result import DownloadResult
from viktor.utils import memoize
from viktor.views import MapResult
from viktor.views import MapView
from viktor.views import WebResult
from viktor.views import WebView

from .map import Map
from .model import BuildingFrame
from .parametrization import SkyCivParametrization
from .skyciv_functions import build_api_object


@memoize
def evaluate_skyciv(api_json: str) -> dict:
    """Creates a SkyCiv API object and sends the functions to the API.
    Also implements our own UserException to the error send by SkyCiv.
    The reason we use the json here and not the ao.request() method is because
    now it is serialised and we can use memoize.

    :param json: The json made by ApiObject.to_json()
    """

    # Send an api request
    response = request(api_json, {"https", 3})  # Send the json to the api
    if response["response"]["status"] != 0:  # The skyciv response status, 0 means no succesful
        raise UserError(response["response"]["msg"])  # Send the skyciv error to the user

    # Evaluate the response
    functions = response["functions"]
    for function in functions:
        if function["function"] == "S3D.results.get":  # Get the correct function out the response
            results = json.dumps(function["data"][0], indent=4)
        if function["function"] == "S3D.model.get":
            model_object = function["data"]  # Get the returned model so we know for sure they match the results
        if function["function"] == "S3D.results.getAnalysisReport":  # Get the correct function out the response
            analysisReport = function["data"]
            url = analysisReport["view_link"]
    return {"results": results, "model": model_object, "url": url}


class SkyCivController(ViktorController):
    label = "Building Frame"
    parametrization = SkyCivParametrization

    def download_solve(self, params, **kwargs):
        """Download button for debugging. Will send a request to skyciv and let you download the solve response."""
        building_frame = BuildingFrame(params)
        building_frame.add_loads()
        api_object = build_api_object(building_frame.model)
        evaluation = evaluate_skyciv(api_object.to_json())
        return DownloadResult(evaluation["results"], "solve.json")

    @WebView("Render", duration_guess=1)
    def get_web_view(self, params, **kwargs):
        """Builds the model and renders it inside the skyciv renderer embedded in the WebView."""
        progress_message(message="Building the model...", percentage=(1 / 2) * 100)
        building_frame = BuildingFrame(params)
        progress_message(message="Rendering...", percentage=(2 / 2) * 100)
        html = building_frame.get_html_render("model")
        return WebResult(html=html)

    @WebView("Results", duration_guess=10)
    def get_results_view(self, params, **kwargs):
        """Get the results from the model and then adds the results to the skyciv renderer embedded in the WebView."""
        progress_message(message="Building the model...", percentage=(1 / 4) * 100)
        building_frame = BuildingFrame(params)  # Build the model
        progress_message(message="Adding loads...", percentage=(2 / 4) * 100)
        building_frame.add_loads()
        progress_message(message="Sending API request...", percentage=(3 / 4) * 100)
        api_object = build_api_object(building_frame.model)
        evaluation = evaluate_skyciv(api_object.to_json())
        building_frame.set(evaluation["model"])  # Update the model with the dict we got from the API
        progress_message(message="Rendering...", percentage=(4 / 4) * 100)
        html = building_frame.get_html_render("results", evaluation["results"])  # Build the html page
        return WebResult(html=html)  # Parse it to the WebView

    @WebView("Analysis Report", duration_guess=10)
    def get_analysis_report(self, params, **kwargs):
        """Get an url from skyciv with the analysis report of the model, then view it inside the WebView."""
        building_frame = BuildingFrame(params)
        building_frame.add_loads()
        api_object = build_api_object(building_frame.model)
        evaluation = evaluate_skyciv(api_object.to_json())
        return WebResult(url=evaluation["url"])

    @MapView("Map View", duration_guess=1)
    def get_map_view(self, params: Munch, **kwargs):
        """Show the building on the map."""
        map_plot = []
        if params.step_design.loc.start:
            map_plot.append(Map(params=params).get_office_polygon())
        return MapResult(map_plot)

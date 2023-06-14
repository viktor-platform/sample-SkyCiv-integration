import os

import requests
import skyciv

from viktor.utils import memoize


def build_api_object(model: skyciv.Model = None, solve: bool = True, save: bool = True) -> skyciv.ApiObject:
    """Initialises the API object and adds the authentication and functions"""
    api_object = skyciv.ApiObject()

    # Authorize using the environment variables, these need to be set. You can get your own token on the your SkyCiv profile page
    secrets = os.environ.get("VIKTOR_APP_SECRET").split(";")
    api_object.auth.username = secrets[0]
    api_object.auth.key = secrets[1]

    # All the functions are found on https://skyciv.com/api/v3/docs/getting-started/. The basic format to add a function is: api_object.functions.add(<function>,{arguments})

    if model is not None:
        # Start the session and set the model
        api_object.functions.add("S3D.session.start", {"keep_open": True})  # Session for the API Call
        api_object.functions.add("S3D.model.set", {"s3d_model": model})  # Select the model

        if solve:
            # Parse functions
            api_object.functions.add("S3D.model.solve", {"analysis_type": "linear"})
            api_object.functions.add("S3D.results.get", {"format": "s3d"})

            # Get analysis report
            api_object.functions.add("S3D.results.getAnalysisReport", {"file_type": "pdf"})

            # Return the model in case skyciv changes it
            api_object.functions.add("S3D.model.get", {})

        # Save the model in our library
        if save:
            api_object.functions.add("S3D.file.save", {"name": "Example viktor", "path": "VIKTOR/"})

    return api_object


@memoize
def get_renderer(url: str = "https://api.skyciv.com/dist/v3/javascript/skyciv-renderer-dist-2.0.0.js") -> str:
    """Get the renderer with the memoize decorator so we can speed up the application."""
    return requests.get(url).content.decode("utf-8")

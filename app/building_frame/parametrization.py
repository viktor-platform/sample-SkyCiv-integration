from viktor.parametrization import BooleanField
from viktor.parametrization import DownloadButton
from viktor.parametrization import GeoPointField
from viktor.parametrization import IntegerField
from viktor.parametrization import Lookup
from viktor.parametrization import NumberField
from viktor.parametrization import OptionField
from viktor.parametrization import Parametrization
from viktor.parametrization import Section
from viktor.parametrization import Step
from viktor.parametrization import Tab
from viktor.parametrization import Text

from .constants import PROFILE_OPTIONS


class SkyCivParametrization(Parametrization):
    # Designing the building
    step_design = Step("Design the building", views=["get_map_view", "get_web_view"])
    step_design.frame = Tab("Frame")

    # office
    step_design.frame.office = Section("Outside dimensions")
    step_design.frame.office.length = NumberField("Total length", min=20, default=20, step=10, max=100, suffix="m")
    step_design.frame.office.width = NumberField("Total width", min=10, default=20, step=10, max=100, suffix="m")
    step_design.frame.office.num_floors = IntegerField("Number of floors", min=2, default=3, step=1, max=20)
    step_design.frame.office.add_braces = BooleanField("Add braces", default=False)

    # columns
    step_design.frame.columns = Section("Frame grid")
    step_design.frame.columns.dist_length = NumberField(
        "Column spacing length", min=1, default=7, step=0.5, max=20, suffix="m"
    )
    step_design.frame.columns.dist_width = NumberField(
        "Column spacing width", min=1, default=7, step=0.5, max=20, suffix="m"
    )

    # materials
    step_design.frame.materials = Section("Sections")
    step_design.frame.materials.columns = OptionField("Columns", options=PROFILE_OPTIONS, default="SHS50x50x4")
    step_design.frame.materials.beams = OptionField("Beams", options=PROFILE_OPTIONS, default="SHS50x50x4")
    step_design.frame.materials.braces = OptionField("Braces", options=PROFILE_OPTIONS, default="SHS50x50x4")

    # Location for wind and snow api
    step_design.loc = Tab("Location")
    step_design.loc.start = GeoPointField(
        "Building corner", description='Use the "Map View" tab to select a point for the building.'
    )
    step_design.loc.rotate = NumberField("Rotate CW", suffix="°", default=0)

    # Call the API
    step_call = Step("Analyze the model", views=["get_analysis_report", "get_results_view"])
    step_call.txt_skyciv = Text("## SkyCiv API request")
    step_call.information = Text(
        "Clicking the reload button will send a request to SkyCiv. If you have provided your own credentials you can also view the model from the [dashboard](https://platform.skyciv.com/dashboard)."
    )
    step_call.self_weight = BooleanField(
        "Self weight", default=True, description="The weight of the materials on the model."
    )
    step_call.snow_load = BooleanField(
        "Snow load", default=False, description="The load of potential snow on the roof of the model."
    )
    step_call.wind_load = BooleanField(
        "Wind load", default=False, description="The pressure of the wind to the side of the model."
    )
    step_call.floor_load = BooleanField(
        "Floor load", default=False, description="The load on the different floors of the model excluding the roof."
    )
    step_call.floor_pressure = NumberField(
        "Weight", default=1, suffix="kg/m^2", step=1, visible=Lookup("step_call.floor_load")
    )
    step_call.download_solve = DownloadButton("Download solve", method="download_solve")

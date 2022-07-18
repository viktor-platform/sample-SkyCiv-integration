import json
from pathlib import Path

import numpy as np
import skyciv
from munch import Munch
from typing_extensions import Literal

from viktor.core import UserException
from viktor.utils import render_jinja_template

from .skyciv_functions import build_api_object
from .skyciv_functions import get_renderer

FLOOR_HEIGHT = 3  # Default height of the floor
SUPPORT = [
    "FFFFFF",  # Fixed Support
    "FFFFFR",  # Pin Support
    "RFFRRR",  # Horizontal Roller
    "FFRRRR",  # Vertical Roller
]
G = -9.81  # Gravity


class BuildingFrame:
    """The reason this class is not a child of skyciv.Model is because when we send an api request we send all the attributes of the model.
    So this will also send our own added attributes, which will cause an error. If you want to make this a child of skyciv.Model you need to
    overwrite the get() method.
    """

    def __init__(self, params: Munch):
        """Initialise the buildingframe with the chosen parameters
        and calculate the grid.
        """
        # Parse the params
        ## Office properties
        self.params = params
        self.length_office = self.params.step_design.frame.office.length
        self.width_office = self.params.step_design.frame.office.width
        self.num_floors = self.params.step_design.frame.office.num_floors

        self.height = FLOOR_HEIGHT * self.num_floors  # Total height of the building

        ## Braces
        self.add_braces = self.params.step_design.frame.office.add_braces  # Check if braces should be added

        # pattern grid
        self.col_dist_length = (
            self.params.step_design.frame.columns.dist_length
        )  # The maximum length the columns can be apart
        self.col_dist_width = (
            self.params.step_design.frame.columns.dist_width
        )  # The maximum width the columns can be apart

        self.grid_num_width = int(self.width_office / self.col_dist_width)  # Number of columns in width
        self.grid_size_width = self.width_office / self.grid_num_width  # Actual distance between columns
        self.grid_num_width += 1  # Add column add the end

        self.grid_num_length = int(self.length_office / self.col_dist_length)  # Number of columns in length
        self.grid_size_length = self.length_office / self.grid_num_length  # Actual distance between columns
        self.grid_num_length += 1  # Add column add the end

        # Materials
        self.column_material = self.params.step_design.frame.materials.columns
        self.beam_material = self.params.step_design.frame.materials.beams
        self.brace_material = self.params.step_design.frame.materials.braces

        # Location
        if self.params.step_design.loc.start:
            self.lat = self.params.step_design.loc.start.lat
            self.lng = self.params.step_design.loc.start.lon
        else:
            self.lat, self.lng = 51.92224690568676, 4.469871725409869

        # Nodal positioning
        self.nodes_per_plain = int(
            self.grid_num_length * self.grid_num_width
        )  # Used for calculating floor position of each node

        ## Corners
        c1 = 0
        c2 = self.grid_num_length - 1
        c3 = self.nodes_per_plain - 1
        c4 = c3 - self.grid_num_length + 1
        self.corner_positions = [c1, c2, c3, c4]

        ## Neighbours of corners
        n1 = (1, self.grid_num_length)
        n2 = (c2 - 1, c2 + self.grid_num_length)
        n3 = (c3 - self.grid_num_length, c3 - 1)
        n4 = (c4 + 1, c4 - self.grid_num_length)
        self.neighbours = [n1, n2, n3, n4]

        # Model
        self.model = self._build_model_from_parameters()

        # Loads
        self.loads = self.params.step_call

    def _build_model_from_parameters(self) -> skyciv.Model:
        """Builds a SkyCiv model with the chosen parameters"""
        model = skyciv.Model("metric")  # Initialise an empty model

        # Member ids:
        # 1: Column
        # 2: Beams
        # 3: Braces

        current_y = 0  # Would be the current height
        for current_floor in range(self.num_floors + 1):
            current_z = 0  # Would be the current "width"
            for _ in range(self.grid_num_width):
                current_x = 0  # Would be the current "length"
                for _ in range(self.grid_num_length):
                    uid = int(
                        model.nodes.add(current_x, current_y, current_z)
                    )  # Add the node to the model and record the id tag
                    if uid > self.nodes_per_plain:  # If the node ID is bigger then the nodes per plain
                        #   then there is a node below it
                        model.members.add(uid - self.nodes_per_plain, uid, 1)  # Connect the node to the node below
                        if (uid - 1) % self.grid_num_length > 0:  # If the column is not the first in its row
                            model.members.add(uid, uid - 1, 2)  # Connect beam in x direction
                        floor_position = (uid - 1) % self.nodes_per_plain  # The id on its own floor
                        if floor_position >= self.grid_num_length:  # If the column is not in the in the column
                            model.members.add(uid, uid - self.grid_num_length, 2)  # Connect beam in z direction
                        if self.add_braces:  # Enable braces on the model
                            for c, n in zip(self.corner_positions, self.neighbours):  # Check for corners
                                if floor_position == c:  # This is a corner
                                    for sn in n:  # Check every neighbor of corner
                                        nid = sn + current_floor * self.nodes_per_plain + 1  # The id of the neighbor
                                        model.members.add(
                                            nid, uid - self.nodes_per_plain, 3
                                        )  # Add brace from neighbor to column of corner
                                        model.members.add(
                                            nid - self.nodes_per_plain, uid, 3
                                        )  # Add brace from column of neighbor to corner
                    else:  # These nodes are on the floor
                        model.supports.add(uid, SUPPORT[0])  # Add support to the floor node
                    current_x += self.grid_size_length  # Increment on the x-axis
                current_z += self.grid_size_width  # Increment on the z-axis
            current_y += FLOOR_HEIGHT  # Increment on the y-axis

        # Add the sections to the skyciv model. We also format the material in our selection to how
        # it is accessed in SkyCiv's library.
        model.sections.add_library_section(["European", "Steel", "EN 10210-2 SHS", self.column_material], 1)
        model.sections.add_library_section(["European", "Steel", "EN 10210-2 SHS", self.beam_material], 1)
        model.sections.add_library_section(["European", "Steel", "EN 10210-2 SHS", self.brace_material], 1)

        # Material
        model.materials.add("Structural Steel")

        return model

    def add_loads(self) -> None:
        """Add different kind of loads to analyse the model"""
        if self.loads.self_weight:
            # Selfweight
            self.model.self_weight.add(y=-1, LG="SW1")
        if self.loads.snow_load:
            # Area loads
            n1 = self.model.nodes.length()
            n2 = n1 - int(self.grid_num_length - 1)
            n3 = n1 + 1 - self.nodes_per_plain
            n4 = n3 + int(self.grid_num_length - 1)
            nodes = [n1, n2, n3, n4]  # The nodes where we want to set the load between
            p = self.get_snow_load()  # Get the snow pressure for the load
            self.model.area_loads.add(type="two_way", nodes=nodes, mag=-p, direction="Y", LG="SNOW")
        if self.loads.wind_load:
            n1 = 1
            n2 = self.grid_num_length
            n3 = n2 + self.nodes_per_plain * self.num_floors
            n4 = n1 + self.nodes_per_plain * self.num_floors
            nodes = [n1, n2, n3, n4]  # The nodes we want to set the load between
            elevations = ""  # This parameter needs to be a string of nodes
            for elevation in np.arange(0, self.num_floors * FLOOR_HEIGHT + FLOOR_HEIGHT, FLOOR_HEIGHT):
                elevations += str(elevation) + ","  # Nodes need to be seperated with a comma
            self.model.area_loads.add(
                type="column_wind_load",
                nodes=nodes,
                mag=1,
                mags="1",
                direction="Y",
                elevations=elevations[:-1],
                column_direction=f"{n1},{n4}",
                LG="WL1",
            )
        if self.loads.floor_load:
            p = (self.loads.floor_pressure * G) * 0.001  # kPa
            for n in range(1, self.num_floors):  # Everyfloor expect ground and roof
                nodes = []  # nodes for the area
                for fp in self.corner_positions:  # Every floor corner position
                    nodes.append(fp + n * self.nodes_per_plain + 1)  # Add this exact node to the area load
                self.model.area_loads.add(type="two_way", nodes=nodes, mag=p, direction="Y", LG=f"AL{n}")

    def get_html_render(self, mode: Literal["model", "results"] = "model", results: str = None):
        """The SkyCiv render is written in javascript. We can use the webview to use it. However the webview only uses a single
        html file. We therefor use the jinja utility to build the html file.
        """

        # We use two renders, one for designing and one for the results
        if not results:
            results = "{}"  # Empty results if we are in the design step

        # Build the html file
        path = Path(__file__).parent.parent / "lib"  # Get the path to the directory of the files we need
        url = (
            "https://api.skyciv.com/dist/v3/javascript/skyciv-renderer-dist-2.0.0.js"  # The url to the skyciv renderer
        )
        renderer = get_renderer(url)  # Request the renderer, uses viktor.utils.memoize so only gets called once
        context = {
            "renderer": renderer,
            "model": self.get(),
            "mode": mode,
            "results": "{{ results }}",
        }  # Create the context to use with jinja
        with open(path / "renderer.html.jinja", "rb") as template:  # Open the html file to be used as jinja template
            filedata = render_jinja_template(template, context)  # Build the html file using the template and context

        # Results can be too big for render_jinja_template, so we do it in two steps
        context = {"results": results}
        with filedata.open_binary() as f:
            filedata = render_jinja_template(f, context)
        return filedata  # The return type of the jinja utility is already an viktor.core.File

    def get_snow_load(self) -> float:
        """Uses the wind and snow calculator from SkyCiv to get the potential pressure of the snow in the given location.
        Because this is an extra api call it will increase the processing time.
        """
        # Build the api object
        ao = build_api_object()

        # Get the template for the arguments for this call
        with open(Path(__file__).parent.parent / "lib" / "load_function_arguments.json") as f:
            arguments = json.load(f)

        # Parse the template
        arguments["site_data"]["lat"] = self.lat
        arguments["site_data"]["lng"] = self.lng
        arguments["building_data"]["building_dimensions"]["length"] = self.length_office
        arguments["building_data"]["building_dimensions"]["width"] = self.width_office
        arguments["building_data"]["building_dimensions"]["ground_to_top"] = self.height

        # Add functions to the call
        ao.functions.add("standalone.loads.start", {"keep_open": True})
        ao.functions.add("standalone.loads.getLoads", arguments)

        # Call the API
        response = ao.request()["response"]
        if response["status"] == 0:
            snow_load = response["data"]["snow_data"]["snow_load"]
        else:
            # If status == 1, skyciv has given an error
            msg = response["msg"]
            raise UserException(msg)

        return snow_load

    def set(self, model_object: dict) -> None:
        """Set individual properties of the model object."""
        self.model.set(model_object)

    def get(self) -> str:
        """Get the json string of the model. Used for the renderer."""
        return json.dumps(self.model.get(), indent=4)

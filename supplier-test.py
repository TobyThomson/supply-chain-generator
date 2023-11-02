# [x] Read in yaml
# [x] Draw a supplier box in GraphViz
# [x] Add country icon to Graphviz!
# [x] Get the recursive behaviour working!
# [x] Add products
# [x] Add links from products to suppliers
# [x] Add material nodes
# [x] Add changes to layout engine
# [x] Get arrowheads working nicely
# [x] Get distance calculation (in terms of tree parsing) working
# [x] Add co2 passing on
# [x] Total Product CO2e calculation
# [x] Add emoji showing transport medium
# [x] Transport CO2e calculation (first pass)

# [ ] Fix the transport calculations so it can handle multiple (product) rescources heading to a supplier
# [ ] Add mass consideration to transport calculations
# [ ] Add processess CO2e calculation

import yaml
import graphviz
import flag
import math

Datafile = "supply-chain-data.yml"

Graph = graphviz.Digraph("supply-chain-diagram", filename="supply-chain-diagram.gv")
Graph.engine="dot"
Graph.format = "svg"
Graph.attr("node", shape="plain")

Font = "Segoe UI Emoji"

MaterialLabelTemplate = """<<TABLE
    ALIGN="CENTER"
    BORDER="0"
    CELLBORDER="1"
    CELLSPACING="0"
    BGCOLOR="coral2">

    <TR>
        <TD><B>{}</B></TD>
    </TR>
</TABLE>>"""

ProductLabelTemplate = """<<TABLE
    ALIGN="CENTER"
    BORDER="0"
    CELLBORDER="1"
    CELLSPACING="0"
    BGCOLOR="cadetblue2">

    <TR>
        <TD><B>{}</B></TD> <TD>{}</TD> <TD>{}</TD>
    </TR>

    <TR>
        <TD COLSPAN="3">{} kg CO2e</TD>
    </TR>
</TABLE>>"""

SupplierLabelTemplate = """<<TABLE
    ALIGN="CENTER"
    BORDER="0"
    CELLBORDER="1"
    CELLSPACING="0"
    BGCOLOR="white">

    <TR>
        <TD><B>{}</B> {}</TD>
    </TR>

    <TR>
        <TD>{}</TD>
    </TR>
</TABLE>>"""

def GenerateMaterialNode(data, pointer):
    label = MaterialLabelTemplate.format(pointer)
    
    Graph.node(pointer, label=label, fontname=Font)

def GenerateProductNode(data, startingNode, pointer, cumulativeCO2e):    
    label = ProductLabelTemplate.format(pointer, data["products"][pointer]["mass"], data["products"][pointer]["quantity"], cumulativeCO2e)
    
    Graph.node(pointer, label=label, fontname=Font)

    arrowhead = "none"

    if pointer == startingNode:
        arrowhead = "normal"
    
    Graph.edge(data["products"][pointer]["supplier"], pointer, arrowhead=arrowhead)

def GenerateSupplierNode(data, pointer, distance, transportMethod):
    flagEmoji = flag.flag(data["suppliers"][pointer]["country-code"])
    processString = "N/A" #"{}".format("<BR/>".join(data["suppliers"][pointer]["processes"]))
    label = SupplierLabelTemplate.format(pointer, flagEmoji, processString)
    
    Graph.node(pointer, label=label, fontname=Font)

    # TODO: Change this so it's not using the same distance for each resocurce coming into the supplier!
    for resource in data["suppliers"][pointer]["resources"]:
        if distance > 0.1:
            Graph.edge(resource, pointer, label=("%.f km (%s)" % (distance, transportMethod)), fontname=Font)

        else:
            Graph.edge(resource, pointer, fontname=Font)

def CalculateTransitEmissions(distance, mass):
    # We assume that any trip that would involve driving for longer than nine hours, as this would complicate logistics, would be taken by air instead (https://www.bluedropservices.co.uk/guides/353/how-long-can-lorry-drivers-drive-for/)
    # We assume average driving speed for heavy good vehicle on the motorway is 60 mph = 97 km/h (https://www.statista.com/statistics/303443/average-speed-on-different-roads-in-great-britain-by-vehicle-type/)
    # Therefore, we assume that the threshold that where air freight becomes preferable over trucking is 9 * 97 = 873 km
    # NOTE: This is an extremly crude method!

    transportMethod = ""
    transport_kgCO2e = 0
    
    if distance < 873:
        # Using trucking emissions factor (in kg CO2e/km/kg of mass transported from here: https://www.co2everything.com/co2e-of/freight-road-truck)
        transportMethod = "🚛"
        transport_kgCO2e = distance * mass * 0.000105

    else:
        # Using air freight emissions factor (in kg CO2e/km/kg of mass transported from here: https://www.co2everything.com/co2e-of/freight-air)
        transportMethod = "✈"
        transport_kgCO2e = distance * mass * 0.00221
    
    return transport_kgCO2e, transportMethod

def SearchTree(data, startingNode, pointer, pointerType, resourceSupplier=None, cumulative_kgCO2e=None):
    if pointerType == "material":
        GenerateMaterialNode(data, pointer)
    
    elif pointerType == "product":
        (resourceSupplier, cumulative_kgCO2e) = SearchTree(data, startingNode, data["products"][pointer]["supplier"], "supplier")

        GenerateProductNode(data, startingNode, pointer, cumulative_kgCO2e)

    elif pointerType == "supplier":
        for resource in data["suppliers"][pointer]["resources"]:
            try:
                materialIndex = data["materials"].index(resource)
                (resourceSupplier, cumulative_kgCO2e) = SearchTree(data, startingNode, data["materials"][materialIndex], "material")

            except ValueError:
                (resourceSupplier, cumulative_kgCO2e) = SearchTree(data, startingNode, resource, "product")

        transportMethod = ""
        distance = 0
        
        if resourceSupplier:
            distance = math.fabs(float(data["suppliers"][pointer]["location"]) - (data["suppliers"][resourceSupplier]["location"]))
            # TODO: Use product mass!
            (transit_kgCO2e, transportMethod) = CalculateTransitEmissions(distance, 1)
            cumulative_kgCO2e = float(cumulative_kgCO2e or 0) + transit_kgCO2e
        
        resourceSupplier = pointer
        
        GenerateSupplierNode(data, pointer, distance, transportMethod)

    return resourceSupplier, cumulative_kgCO2e

def main():
    with open(Datafile, "r") as file:
        data = yaml.safe_load(file)

        startingNode = "product1"
        SearchTree(data, startingNode, startingNode, "product")
        
    Graph.view()

if __name__ == "__main__":
    main()
import yaml
import graphviz
import flag
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import random

Datafile = "supply-chain-data.yml"

Geolocator = Nominatim(user_agent="supply-chain-generator-app")

Graph = graphviz.Digraph("supply-chain-diagram", filename="supply-chain-diagram.gv")
Graph.engine="dot"
Graph.format = "svg"

Graph.attr("node", shape="plain")
Graph.attr("graph", ranksep="1")
Graph.attr("graph", splines="true")

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
        <TD COLSPAN="3">{:.4f} kg CO2e</TD>
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
</TABLE>>"""

def GenerateMaterialNode(data, material):
    label = MaterialLabelTemplate.format(material)
    
    Graph.node(material, label=label, fontname=Font)

def GenerateProductNode(data, startingProduct, product, cumulative_kgCO2e):    
    label = ProductLabelTemplate.format(product, data["products"][product]["mass_g"], data["products"][product]["quantity"], float(cumulative_kgCO2e or 0))
    
    Graph.node(product, label=label, fontname=Font)

    arrowhead = "none"

    if product == startingProduct:
        arrowhead = "normal"
    
    Graph.edge(data["products"][product]["supplier"], product, arrowhead=arrowhead)

def GenerateSupplierNode(data, supplier):
    countryCode = Geolocator.geocode(data["suppliers"][supplier]["address"], addressdetails=True).raw["address"]["country_code"]

    flagEmoji = flag.flag(countryCode)
    # Uncomment the below when it comes time to add the process emissions stuff back in
    #processString = "{}".format("<BR/>".join(data["suppliers"][pointer]["processes"]))
    label = SupplierLabelTemplate.format(supplier, flagEmoji) #, processString)
    
    Graph.node(supplier, label=label, fontname=Font)

def GenerateSupplierEdge(supplier, resource, distance_km=None, transportMethod=None):
    if not distance_km or not transportMethod or distance_km < 0.1:
        Graph.edge(resource, supplier, fontname=Font)
    
    else:
        Graph.edge(resource, supplier, label=("%.f km (%s)" % (distance_km, transportMethod)), fontname=Font)

def CalculateTransitEmissions(distance_km, mass_g):
    # We assume that any trip that would involve driving for longer than nine hours, as this would complicate logistics, would be taken by air instead (https://www.bluedropservices.co.uk/guides/353/how-long-can-lorry-drivers-drive-for/)
    # We assume average driving speed for heavy good vehicle on the motorway is 60 mph = 97 km/h (https://www.statista.com/statistics/303443/average-speed-on-different-roads-in-great-britain-by-vehicle-type/)
    # Therefore, we assume that the threshold that where air freight becomes preferable over trucking is 9 * 97 = 873 km
    # NOTE: This is an extremly crude method!

    transportMethod = ""
    transport_kgCO2e = 0
    
    if distance_km < 873:
        # Using trucking emissions factor (in kg CO2e/km/g of mass transported from here: https://www.co2everything.com/co2e-of/freight-road-truck)
        transportMethod = "🚛"
        transport_kgCO2e = distance_km * mass_g * 0.000000105

    else:
        # Using air freight emissions factor (in kg CO2e/km/g of mass transported from here: https://www.co2everything.com/co2e-of/freight-air)
        transportMethod = "✈"
        transport_kgCO2e = distance_km * mass_g * 0.00000221
    
    return transport_kgCO2e, transportMethod

def SearchTree(data, startingNode, pointer, pointerType, resourceSupplier=None, cumulative_kgCO2e=None):
    if pointerType == "material":
        GenerateMaterialNode(data, pointer)
    
    elif pointerType == "product":
        (resourceSupplier, cumulative_kgCO2e) = SearchTree(data, startingNode, data["products"][pointer]["supplier"], "supplier")

        GenerateProductNode(data, startingNode, pointer, cumulative_kgCO2e)

    elif pointerType == "supplier":
        GenerateSupplierNode(data, pointer)

        for resource in data["suppliers"][pointer]["resources"]:
            try:
                materialIndex = data["materials"].index(resource)
                (resourceSupplier, cumulative_kgCO2e) = SearchTree(data, startingNode, data["materials"][materialIndex], "material")

            except ValueError:
                (resourceSupplier, cumulative_kgCO2e) = SearchTree(data, startingNode, resource, "product")
            
            if resourceSupplier:
                supplier0Location = Geolocator.geocode(data["suppliers"][pointer]["address"])
                supplier1Location = Geolocator.geocode(data["suppliers"][resourceSupplier]["address"])

                if not supplier0Location:
                    print("CANNOT RESOLVE ADDRESS %s FOR SUPPLIER %s. BROADEN ADDRESS TO FIX" % (data["suppliers"][pointer]["address"], pointer))
                    exit()
                
                if not supplier1Location:
                    print("CANNOT RESOLVE ADDRESS %s FOR SUPPLIER %s. BROADEN ADDRESS TO FIX" % (data["suppliers"][resourceSupplier]["address"], resourceSupplier))
                    exit()

                distance_km = geodesic((supplier0Location.latitude, supplier0Location.longitude), (supplier1Location.latitude, supplier1Location.longitude)).kilometers

                # NOTE: The following assumes the resource is a product and not a material.
                #       I think we get away with it because "resourceSupplier" should be
                #       "None" if the resource was a material (and thus none of this is called)
                (transit_kgCO2e, transportMethod) = CalculateTransitEmissions(distance_km, data["products"][resource]["mass_g"])
                cumulative_kgCO2e = float(cumulative_kgCO2e or 0) + transit_kgCO2e

                GenerateSupplierEdge(pointer, resource, distance_km, transportMethod)
            
            else:
                GenerateSupplierEdge(pointer, resource)
        
        resourceSupplier = pointer
    
    return resourceSupplier, cumulative_kgCO2e

def main():
    with open(Datafile, "r") as file:
        data = yaml.safe_load(file)

        startingNode = "iPhone X"
        SearchTree(data, startingNode, startingNode, "product")
        
    Graph.view()

if __name__ == "__main__":
    main()
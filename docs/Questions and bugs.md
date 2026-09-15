# Questions and bugs

1. Should I change common to Administrative boundaries?
	- Where should I leave landcover classes, DSM, DEM, calculation tables?


2. How to populate the table of Supply and Demand for housing?

    - Currently, I have a yearly stock balance and new constructions authorized per year. But not the real demand of housing

3. How to populate building address from Ligplaats? 
	- Property info is still not connected, how to get it and connect to building?


4. On Config.js / Tool Categories, should the admin layer be always available? this is for indicators grouping but makes pop up queries hard

5. How to populate LandCover? BRT Landuse is vector. I can process to translate to raster but.... how long would that take?

6. PDOK doesn't serve EP-Online energy labels anymore. EP-online uses API per building, which would create thousands of api calls. How to incorporate this then? --- I have 2022 data for now from Atlaseefomgeving

7. Should Energy labels be imported automatically when importing buildings? or separately?


8. How to add the raster source data in database (date of acquisition, clouds, etc)?

9. DEM//DSM are too large (0.5m resolution) -- to store in COG and operate we lose the ability to run server-side raster SQL (clip/stats-by-geometry) against DEM/DSM directly in Postgres. Option 2 is Rasterio but slower


10. openEO has a server for "Dynamic Land Cover" based on the sentinel 1 and 2 data. It uses Random forest and own model to calculate. It cost credits. How to deal with costs?
    - Should I import external functions to get the landcover classes using ML?

11. GEE authenthification is still an issue, I can not get to connect to the gee server and test the retrievals

12. Does energy label is the only layer on energy? should I add something like solar panels wind turbines etc?
    - Should I connect this with Johannes electricity thingy?

13. Should I eliminate groundwater? I dont do much with it

14. should I explore if underground navigation is possible?

14. Green spaces and parks are saved in two models, should I merge them into one? Probably only green spaces

## TODOS

1. CHECK FOR IMPROVING AND ADDING INDICES FROM NEW RESEARCH EXAMPLE NDWI - I know there are betters.
2. Have overview of active layers
2. Create an update button to search changes in the database to 

2. -Max 10% cloud coverage-

2. Check from Destination Earth -------- This is 5km scale

2. Climate Atlas -- Check Maps and updates.... 

3. Pre write outputs

4. Howq to create alarmns and messages to give instant things ---

5. Check with Carolina Pereria --- See her appwith climate data. --- This is WBGT only, and quick proxy. Requires getting a CSV and parsing to the stations. Might be easy.


5. **See the kind of choices and steps on the development .... Write Methodology for paper --- What are the different steps you do and why?**

5. Work with mila to see how everyone is doing it?? --- Rakibun example

3. on nature/models/Park, Import parks --- where to store?
3. on builtup/models/facilities, How to import from OSM or GoogleMaps?
3. on builtup/models/Property, add Define green visibility index and calculation method
3. define where to store zoning data and how to import
3. Add policy options and restriction in pop up
3. verify functions of water supply to render HTMX
3. Get data for water, or mock it up
3. How to calculate changes on land cover and then calculate inflitration changes? reflection changes, etc?

3. create HTMX for indicators of built up
3. How to connect buildings and properties to housing? --- check woonfuctie
3. create HTMX for indicators of housing 
4. create HTMX for indicators of energy
4. Create live stream of weather data 
    - move indicator of weather to top
    - see if mapbox rain render can be activated live with this
    - How to connect with weather stations?
5. create functions for LST, PET, SVF, SUHHI calculations - see Soliweg or similar
6. create HTMX for indicators of nature 

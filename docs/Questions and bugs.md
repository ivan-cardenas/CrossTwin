# Questions and bugs

1. I changed common to Administrative boundaries?
	- Where should I leave landcover classes, DSM, DEM, calculation tables?


2. How to populate the table of Supply and Demand for housing?

    - Currently, I have a yearly stock balance and new constructions authorized per year. But not the real demand of housing

3. How to populate building address from Ligplaats? 
	- Property info is still not connected, how to get it and connect to building?


4. On Config.js / Tool Categories, should the admin layer be always available? this is for indicators grouping but makes pop up queries hard

5. How to populate LandCover? BRT Landuse is vector. I can process to translate to raster but.... how long would that take?
 - I need to use raster to make operations of landcover change, infiltratrion, albedo, etc.

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

14. is there a table or map of infiltration capacity?

14. should I use docker for deployment?

14. The urbanization degree is defined by CBS as the number of addresses per square kilometre. Should I calculate it like that? I am more interested in urban sprawl growth. How to add this?
    
    Degree of urbanisation
    The classification of surrounding address density based on five categories:
    - extremely urbanised: 2,500 addresses or more per square kilometre;
    - strongly urbanised: 1,500 to 2,500 addresses per square kilometre;
    - moderately urbanised: 1,000 to 1,500 addresses per square kilometre;
    - hardly urbanised: 500 to 1,000 addresses per square kilometre;
    - not urbanised: fewer than 500 addresses per square kilometre. 

14. On which sector should I leave Population Density Raster?


14. Explore how to include the DB models to be read with an LLM to be able to reply questions about the data in the database. So check the structure, then search on database, then reply to the user.

14. add CO2 emissions per building and Sentinel 5 

14. Check Voxelmates for scalable voxelization --- This is a company
    - Optimized octreee data structure  for hierachachy 
    - they work in sqlite so it runs on the database - can it be moved to postgres and run on the server?

14. Create a script that checks if there is a database existent and if not, it creates one. 

14. Add a browser for projects, so DT of city A, DT of city B, etc. Each city is a DB.

14. It is possible to implement urban heat walkability index  see picture. 

14. There is a library of NBS for urban heat mitigation. Should I add them to the database for LLM possible solutions/interventions and recomendations.

20. LIMITATION --  THE SYSTEM USE RELATIONAL DATABASES AND MULTIPLE TABLES. SO SPEED OF JOINS CAN BE AN ISSUE. MAYBE USING NODE4J OR GRAPHDB IS A BETTER OPTION
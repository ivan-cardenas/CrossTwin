# Known Issues and possible solutions

## Google Earth Engine credentials not working
If you face the issue `GEE authentication failed: Caller does not have required permission to use project`, make sure your service account has the required permissions.

The error you are encountering occurs because Google Earth Engine (GEE) needs to verify service usage against your project `<Your Project>`. To resolve this, you must ensure that the Service Usage API is enabled on the project and that the caller (your user account or service account) has the Service Usage Consumer role.

Here are the step-by-step instructions and commands to fix this issue:

**Step 1: Enable the Service Usage API**

The Service Usage API must be enabled on your project to track and allow API consumption.

Run the following command in **the cloud shell** an account with project editor or owner permissions:

    gcloud services enable serviceusage.googleapis.com --project=ee-cygnus26

**Step 2: Grant the Service Usage Consumer Role**

Grant the caller (the identity experiencing the authentication failure) the Service Usage Consumer (roles/serviceusage.serviceUsageConsumer) role.

Run the following command, replacing `<CALLER_IDENTITY>` with the specific user email or service account email (e.g., user:your-email@gmail.com or serviceAccount:your-sa@ee-cygnus26.iam.gserviceaccount.com):

    gcloud projects add-iam-policy-binding ee-cygnus26 \
        --member="<CALLER_IDENTITY>" \
        --role="roles/serviceusage.serviceUsageConsumer"

Wait 2–3 minutes for IAM propagation before retrying your Google Earth Engine authentication or request.


## LST calculation

LST calculation follow a method from Bobalova et al. (2026). This method uses Landsat Imagery to calculate LST with the help of NDVI-based emissivity. However, to simulate modifications of land cover and vegetation, the NDVI stored in `urban_heat.NDVI` is used. For instance Creation of buildings in `built-up` layer will modify landcover and NDVI, then LST gets re-calculated.

```
@article{BOBALOVA20263281,
title = {Improving Landsat land surface temperature estimation in Google Earth Engine using NDVI-based emissivity},
journal = {Advances in Space Research},
volume = {77},
number = {3},
pages = {3281-3299},
year = {2026},
issn = {0273-1177},
doi = {https://doi.org/10.1016/j.asr.2025.11.085},
url = {https://www.sciencedirect.com/science/article/pii/S0273117725013699},
author = {Hana Bobáľová and Šimon Opravil},
keywords = {Land surface temperature, Landsat, Google Earth Engine, Land surface emissivity, NDVI},
abstract = {Land surface temperature (LST) data derived from satellite images are important for various applications, including mapping urban heat islands, analysing temporal and spatial temperature patterns, assessing the cooling effect of urban greenery, and developing population vulnerability indices for heat waves. Thermal sensors aboard Landsat satellites provide the most spatially detailed data with the longest temporal continuity. Landsat Surface Temperature (ST) is already available as a standard product, and a code for estimating the Landsat LST using the empirical statistical mono-window method has been implemented in the Google Earth Engine (GEE). However, these approaches rely on the ASTER Global Emissivity Dataset, which has certain limitations, including missing values. In GEE, we developed an approach to calculate land surface emissivity using various NDVI-based methods, combined with the statistical mono-window and radiative transfer equation methods for LST calculation. Developed code provides the creation of seamless LST products without unnatural block artifacts, reflecting the current land cover and vegetation condition. Validation against in situ measurements from the SURFRAD network revealed that the statistical mono-window method proved to be more accurate than the Landsat ST product and radiative transfer equation methods, regardless of the emissivity data source. The NDVI-based emissivity combined with the statistical mono-window method yielded higher LST precision than the approach using ASTER GED emissivity. These results were consistent across all Landsat missions. Furthermore, we demonstrate that the lowest accuracy is achieved in calculating LST on mixed surfaces and the highest on bare soil. The overestimation of satellite LST measurements at high temperatures was only apparent on mixed and vegetated surfaces, while it was more pronounced in the Landsat ST product and other radiative transfer equation methods. These findings and the publicly available GEE code can lead to more accurate LST mapping and analysis results.}
}
```
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
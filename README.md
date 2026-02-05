# CrossTwin

A Django-based digital twin mapping application for visualizing and managing geospatial data. CrossTwin provides a comprehensive platform for working with spatial data, featuring interactive mapping, sophisticated data import capabilities, and dynamic layer visualization.

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![Django](https://img.shields.io/badge/django-5.x-green)
![Python](https://img.shields.io/badge/python-3.x-blue)
![PostGIS](https://img.shields.io/badge/PostGIS-enabled-orange)

## 🌟 Features

### Interactive Mapping
- **Mapbox Integration**: High-performance interactive mapping with Mapbox GL JS
- **3D Building Visualization**: Advanced 3D extrusion for building structures
- **Dynamic Layer Management**: Real-time layer toggling and filtering
- **Category-Based Filtering**: Organize layers by Heat, Green, Water, and Groundwater categories
- **Live Layer Counts**: Real-time statistics for each data category

### Data Import System
- **Multi-Format Support**: Import GeoJSON and Shapefile formats
- **Intelligent Field Mapping**: Dynamic form generation with model field help text
- **SRID Configuration**: Proper coordinate reference system handling (EPSG:28992 - Dutch RD New)
- **Preview & Validation**: Data preview before final import
- **Transaction Safety**: Savepoint-based error handling for reliable imports

### Urban Twin Interface
- **Dark Glassmorphism Theme**: Modern, polished UI with themed components
- **Responsive Design**: Mobile-friendly interface using Tailwind CSS
- **Icon Integration**: Bootstrap Icons for consistent visual language
- **Progressive Enhancement**: Smooth animations and transitions

### Architecture
- **Model Registry Pattern**: Automatic layer discovery without manual configuration
- **Generic API Endpoints**: Leverage existing model structures dynamically
- **Modular App Structure**: Organized by functional areas (Heat, Green, Water, Groundwater)
- **Spatial Data Models**: PostgreSQL with PostGIS for efficient spatial queries

## 📋 Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Key Concepts](#key-concepts)
- [Usage](#usage)
- [Data Models](#data-models)
- [API Endpoints](#api-endpoints)
- [Troubleshooting](#troubleshooting)
- [Development Notes](#development-notes)

## 🔧 Requirements

### System Requirements
- Python 3.8+
- PostgreSQL 12+ with PostGIS extension
- GDAL/OGR libraries (for spatial data processing)
- Node.js (for frontend tooling, optional)

### Python Dependencies
```
Django==5.x
psycopg2-binary
geopandas
shapely
fiona
pyproj
djangorestframework
```

### PostGIS Version Compatibility
- Ensure PostGIS version matches between system and Python environment
- PROJ library version should be consistent across installations
- Recommended: PostGIS 3.x with PROJ 9.x

## 📦 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/crosstwin.git
cd crosstwin
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Set Up PostgreSQL with PostGIS
```bash
# Create database
createdb digitaltwin

# Enable PostGIS extension
psql -d digitaltwin  -c "CREATE EXTENSION postgis;"
```

### 5. Configure Environment Variables
Create a `.env` file in the project root:
```env
SECRET_KEY=your-secret-key-here
DEBUG=True
DATABASE_NAME=crosstwin_db
DATABASE_USER=your_db_user
DATABASE_PASSWORD=your_db_password
DATABASE_HOST=localhost
DATABASE_PORT=5432
MAPBOX_ACCESS_TOKEN=your_mapbox_token

COORDINATE_SYSTEM=28992 # EPSG code for Dutch RD New
```

### 6. Run Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Create Superuser
```bash
python manage.py createsuperuser
```

### 8. Run Development Server
```bash
python manage.py runserver
```

Visit `http://localhost:8000` to access the application.

## ⚙️ Configuration

### Coordinate Reference System
CrossTwin uses **EPSG:28992** (Dutch RD New) as the default coordinate system. This is configured in the spatial models and import system.

To change the default SRID:
1. Update `COORDINATE_SYSTEM` in the `.env` file
2. Modify the importer's SRID configuration
3. Update Mapbox projection settings if needed

### Mapbox Configuration
1. Obtain a Mapbox access token from https://www.mapbox.com/
2. Add the token to your `.env` file
3. Update the Mapbox style URL in templates if using custom styles

## 📁 Project Structure

```
crosstwin/
├── DigitalTwin/              # Project configuration
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── importer/               # Data import application
│   ├── models.py
│   ├── views.py
│   ├── forms.py
│   ├── utils.py
│   └── templates/
│       └── importer/
│           ├── upload.html
│           ├── map_fields.html
│           ├── preview.html
│           └── success.html
├── heat/                   # Heat-related spatial data
│   ├── models.py
│   └── admin.py
├── green/                  # Green infrastructure data
│   ├── models.py
│   └── admin.py
├── watersupply/                  # Water supply infrastructure
│   ├── models.py
│   └── admin.py
├── groundwater/            # Groundwater data
│   ├── models.py
│   └── admin.py
├── core/                   # Core functionality
│   ├── registry.py         # Model registry pattern
│   └── utils.py
├── api/                    # API endpoints
│   ├── views.py
│   └── serializers.py
├── common/                 # Common models
│   ├── models.py
│   └── admin.py
│   ├── static/
│   │   └── styles.css      # Custom styles
│   |   |└── js/
│           └── map.js          # Mapbox initialization
└── templates/
    ├── base.html
    └── map.html
```

## 💡 Key Concepts

### Model Registry Pattern
CrossTwin uses a centralized registry to automatically discover and manage spatial models:

```python
# core/registry.py
MODEL_REGISTRY = {
    'City': City,
    'Neighborhood': Neighborhood,
    'Region': Region,
    # ... automatically populated
}
```

This pattern enables:
- Dynamic layer discovery
- Generic API endpoints
- Automatic form generation
- Consistent data access patterns

### Dynamic Layer Management
Layers are automatically categorized based on Django app labels:
- `heat.*` → Heat category
- `green.*` → Green category
- `water.*` → Water category
- `groundwater.*` → Groundwater category

### Spatial Data Flow
1. **Import**: Upload GeoJSON/Shapefile → Parse → Map fields
2. **Storage**: Transform to EPSG:28992 → Store in PostGIS
3. **Retrieval**: Query PostGIS → Serialize to GeoJSON
4. **Display**: Load in Mapbox → Render layers

## 🚀 Usage

### Importing Data

#### Step 1: Upload File
Navigate to `/importer/upload/` and upload a GeoJSON or Shapefile:
- Supported formats: `.geojson`, `.json`, `.zip` (for shapefiles)
- File size limit: 50MB

#### Step 2: Map Fields
The system displays:
- Source fields from your file
- Target model fields with help text
- Field type indicators (required/optional)

Map your source fields to the appropriate target fields.

#### Step 3: Preview
Review the data mapping:
- Sample records displayed
- Field mapping summary
- Validation warnings/errors

#### Step 4: Import
Confirm and import. The system will:
- Transform geometries to EPSG:28992
- Validate data types
- Create database records
- Update layer registry

### Viewing Data on Map

1. Navigate to the main map view
2. Use the toolbar to:
   - Toggle layers on/off
   - Filter by category
   - View layer information
   - Enable 3D building mode

3. Interact with features:
   - Click on features for details
   - Zoom and pan
   - Switch base maps

### Working with the API

#### Get All Layers
```bash
curl http://localhost:8000/api/layers/
```

#### Get Specific Layer Data
```bash
curl http://localhost:8000/api/layers/<model_name>/
```

Response format:
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { ... },
      "properties": { ... }
    }
  ]
}
```

## 🗄️ Data Models

### Base Spatial Model
All spatial models inherit common fields:
```python
class BaseSpatialModel(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    geom = models.GeometryField(srid=28992)
    updated_at = models.DateTimeField(auto_now=True)
```

### Example Models

#### City
```python
class City(models.Model):
    name = models.CharField(max_length=255)
    population = models.IntegerField(null=True, blank=True)
    area = models.FloatField(null=True, blank=True)
    geom = models.MultiPolygonField(srid=28992)
```

#### Water Infrastructure
```python
class WaterSupplyLine(models.Model):
    line_id = models.CharField(max_length=100)
    diameter = models.FloatField()
    material = models.CharField(max_length=50)
    installation_date = models.DateField()
    geom = models.LineStringField(srid=28992)
```

## 🔌 API Endpoints

### Layer Management
- `GET /api/layers/` - List all available layers
- `GET /api/layers/<model_name>/` - Get GeoJSON for specific layer

### Import System
- `POST /importer/upload/` - Upload data file
- `POST /importer/map-fields/` - Map fields to model
- `GET /importer/preview/` - Preview mapped data
- `POST /importer/import/` - Execute import

### Utility Endpoints
- `GET /api/layer-info/<model_name>/` - Get layer metadata
- `GET /api/categories/` - List layer categories

## 🐛 Troubleshooting

### PROJ Library Version Mismatch
**Symptom**: Errors like "PROJ version mismatch" during import

**Solution**:
1. Check PROJ versions:
   ```bash
   python -c "import pyproj; print(pyproj.proj_version_str)"
   psql -d crosstwin_db -c "SELECT PostGIS_PROJ_Version();"
   ```

2. Ensure versions match or use PostGIS's native functions:
   ```python
   # Use ST_AsGeoJSON instead of GDAL
   geojson = connection.cursor().execute(
       "SELECT ST_AsGeoJSON(geom) FROM table"
   )
   ```

### Import Failures
**Symptom**: Data not importing despite valid file

**Check**:
1. File encoding (should be UTF-8)
2. Geometry validity (`ST_IsValid`)
3. SRID compatibility
4. Required field mappings
5. PostgreSQL logs for constraint violations

### Mapbox Not Loading
**Symptom**: Map container is blank

**Check**:
1. Mapbox access token is valid
2. Console for JavaScript errors
3. Network tab for failed requests
4. API endpoint responses

### Missing Layers in Map
**Symptom**: Imported data not appearing

**Check**:
1. Layer is registered in `MODEL_REGISTRY`
2. API endpoint returns valid GeoJSON
3. Layer extent matches map viewport
4. Layer visibility toggle state

## 📝 Development Notes

### Best Practices
1. **Always use savepoints** for transactional imports
2. **Validate geometries** before import using `ST_IsValid`
3. **Handle SRID transformations** explicitly
4. **Use help_text** in model fields for better UX
5. **Prefer dynamic solutions** over hardcoded configurations

### Code Organization
- Keep spatial logic in model methods
- Use class-based views for consistency
- Separate concerns: views, forms, utilities
- Document complex spatial operations

### Performance Considerations
- Use spatial indexes on geometry fields
- Implement pagination for large datasets
- Cache layer metadata
- Optimize GeoJSON serialization

### Testing
```bash
# Run tests
python manage.py test

# Test specific app
python manage.py test importer

# Test with coverage
coverage run --source='.' manage.py test
coverage report
```

## 🎨 Frontend Development

### Styling Architecture
- **Tailwind CSS**: Utility-first framework
- **Custom CSS**: Theme variables and animations in `styles.css`
- **CSS Properties**: For dynamic theming
  ```css
  :root {
    --glass-bg: rgba(17, 24, 39, 0.8);
    --glass-border: rgba(255, 255, 255, 0.1);
  }
  ```

### JavaScript Architecture
- External JS files for better organization
- Modular approach with initialization functions
- Event delegation for dynamic content
- Mapbox GL JS for mapping

## 🔐 Security Considerations

1. **Database**: Use strong passwords, restrict access
2. **API**: Implement authentication for production
3. **File Uploads**: Validate file types and sizes
4. **CSRF**: Django CSRF protection enabled
5. **Environment**: Never commit `.env` files

## 🚧 Roadmap

### Planned Features
- [ ] User authentication and permissions
- [ ] Advanced spatial analysis tools
- [ ] Time-series data visualization
- [ ] Export functionality (GeoJSON, Shapefile, KML)
- [ ] Collaborative editing
- [ ] Mobile app
- [ ] Integration with external data sources
- [ ] Advanced search and filtering
- [ ] Custom style editor
- [ ] Automated data validation rules

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Mapbox** for mapping infrastructure
- **PostGIS** for spatial database capabilities
- **GeoPandas** for spatial data processing
- **Django** for the robust web framework

## 📞 Support

For issues and questions:
- Open an issue on GitHub
- Contact: [i.l.cardenasleon@utwente.nl](mailto:i.l.cardenasleon@utwente.nl)
- Documentation: [link to docs]

---

**Built with ❤️ for geospatial data management**
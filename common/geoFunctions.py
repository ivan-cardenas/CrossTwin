from django.contrib.gis.measure import Area
from django.apps import apps
from django.contrib.gis.db import models

def get_area(self): 
        """ 
        Returns the area in square kilometers. 
        """
        area_sqkm = self.polygon.area.sq_km
      

        return area_sqkm



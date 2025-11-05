from django.contrib.gis.measure import Area

def get_area(self): 
        """ 
        Returns the area in square kilometers. 
        """
        area_sqkm = self.polygon.area.sq_km
      

        return area_sqkm





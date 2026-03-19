from pyproj import Transformer

transformer = Transformer.from_crs("EPSG:3907", "EPSG:4326", always_xy=True)
lon, lat = transformer.transform(5601571, 5167496) # East, North
print(lat, lon)
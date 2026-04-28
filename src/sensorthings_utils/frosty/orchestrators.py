"""Orchestrate complex interactions with FROST server instances."""
#standard
#external
#internal

from sensorthings_utils.config import FROST_ROOT_DEFAULT, FROST_VERSION_DEFAULT
from sensorthings_utils.frosty.post import make_frost_entity
from sensorthings_utils.frosty.types import FrostUrl
from sensorthings_utils.sensor_things.extensions import SensorConfig
from sensorthings_utils.sensor_things.schema import SensorThingsEntity, SensorThingsEntityGroups


def initial_setup(
        sensor_config: SensorConfig, 
        root_url:str=FROST_ROOT_DEFAULT,
        version:str = FROST_VERSION_DEFAULT
        ) -> list[FrostUrl] | None:

    created_urls = []
    # create a sensor
    sensors = (sensor_config.st_objects[SensorThingsEntity.SENSOR])
    #TODO: handle existence
    if len(sensors) > 1:
        raise AttributeError(f"More than 1 sensor in {sensor_config._filepath}")
    for sensor in sensors:
        sensor_url = make_frost_entity(sensor, root_url, version) 
    # create the datastream/s
    datastreams = (sensor_config.st_objects[SensorThingsEntity.DATASTREAM])
    for datastream in datastreams:
        make_frost_entity(datastream, root_url, version, endpoint=sensor_url)
        #make the observed property (there is 1)
        #make the sensor (there is 1)
        #make the thing (there is 1)
            #make the thing's locations (there are n)


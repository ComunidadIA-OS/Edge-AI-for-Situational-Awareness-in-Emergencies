export type WeatherCurrent = {
  time: string;
  temperature_2m: number;
  relative_humidity_2m: number;
  wind_speed_10m: number;
  wind_direction_10m: number;
  wind_gusts_10m: number;
  weather_code: number;
};

export type WeatherResponse = {
  latitude: number;
  longitude: number;
  timezone: string;
  current: WeatherCurrent;
};

export type WindVector = {
  lon: number;
  lat: number;
  u: number;
  v: number;
};

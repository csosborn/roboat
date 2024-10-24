# Power System

## Component Selection

### Battery
- [Epoch 12v 50Ah LiFePo4 battery](https://www.epochbatteries.com/products/12v-50ah-bluetooth-lifepo4-deep-cycle-battery-epoch-essentials
)
- 14.3 lbs
- 7.75" long, 6.5" wide, 7" tall
- 600Wh

### Charge Controller
- Option 1: [Genasun GVB-8-Li-14.2V MPPT controller](https://cdn.shopify.com/s/files/1/0062/2959/0114/files/GVB-8_Manual.pdf?v=1680700571)
  - Min panel voltage: 5V
  - Max panel current: 8A
  - Max panel power: 105W
  - Min battery voltage: 9V
  - Efficiency: 0.95 to 0.97 (max delivered power ~100W)
- Option 2: [Genasun GV-10-Li-14.2V MPPT controller](https://sunforgellc.com/wp-content/uploads/2022/04/GV-10_Manual-rev.4.1-2021-2022_AP.pdf)
  - Min panel voltage: ~15V
  - Max panel current: 10A
  - Max panel power: 140W

### Solar Array

- [Sunpower Maxeon 3.6W C60 cells](https://fullbattery.com/products/sunpower-c60-solar-cell)
  - Voc 0.6V
  - Isc 6A
  - 125mm x 125mm
- Option 1: 27 cells in a 3 x 9 array
  - 16.2V, 6A total
  - 97W total
  - min array size: 1.125m x 0.375m
- Option 2: 32 cells in a 4 x 8 array
  - 19.2V, 6A total
  - 115W total
  - min array size: 1m x 0.5m

### Power Monitoring
- [INA260 voltage/current sensor](https://www.adafruit.com/product/4226) for battery voltage and net current

## System Performance

In full sun and perfect conditions, the solar array will produce around 90W (a guess, adjusting for losses in the epoxy encapsulant). At this rate, fully charging the battery would take approximately 7 hours, and yield 600Wh. This is a reasonable guess for the amount of energy available per day, with good days yielding somewhat more. 

The larger Option 2 array will behave similarly, but with about 18% more energy available per day.
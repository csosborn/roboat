from machine import I2C
from micropython import const
import ustruct

_REG_CONFIG = const(0x00)  # CONFIGURATION REGISTER (R/W)
_REG_CURRENT = const(0x01)  # SHUNT VOLTAGE REGISTER (R)
_REG_BUSVOLTAGE = const(0x02)  # BUS VOLTAGE REGISTER (R)
_REG_POWER = const(0x03)  # POWER REGISTER (R)
_REG_MASK_ENABLE = const(0x06)  # MASK ENABLE REGISTER (R/W)
_REG_ALERT_LIMIT = const(0x07)  # ALERT LIMIT REGISTER (R/W)
_REG_MFG_UID = const(0xFE)  # MANUFACTURER UNIQUE ID REGISTER (R)
_REG_DIE_UID = const(0xFF)  # DIE UNIQUE ID REGISTER (R)

class Mode:
    """Modes avaible to be set

    +--------------------+---------------------------------------------------------------------+
    | Mode               | Description                                                         |
    +====================+=====================================================================+
    | ``Mode.CONTINUOUS``| Default: The sensor will continuously measure the bus voltage and   |
    |                    | shunt voltage across the shunt resistor to calculate ``power`` and  |
    |                    | ``current``                                                         |
    +--------------------+---------------------------------------------------------------------+
    | ``Mode.TRIGGERED`` | The sensor will immediately begin measuring and calculating current,|
    |                    | bus voltage, and power. Re-set this mode to initiate another        |
    |                    | measurement                                                         |
    +--------------------+---------------------------------------------------------------------+
    | ``Mode.SHUTDOWN``  |  Shutdown the sensor, reducing the quiescent current and turning off|
    |                    |  current into the device inputs. Set another mode to re-enable      |
    +--------------------+---------------------------------------------------------------------+

    """

    SHUTDOWN = const(0x0)
    TRIGGERED = const(0x3)
    CONTINUOUS = const(0x7)

class ConversionTime:
    """Options for ``current_conversion_time`` or ``voltage_conversion_time``

    +----------------------------------+------------------+
    | ``ConversionTime``               | Time             |
    +==================================+==================+
    | ``ConversionTime.TIME_140_us``   | 140 us           |
    +----------------------------------+------------------+
    | ``ConversionTime.TIME_204_us``   | 204 us           |
    +----------------------------------+------------------+
    | ``ConversionTime.TIME_332_us``   | 332 us           |
    +----------------------------------+------------------+
    | ``ConversionTime.TIME_588_us``   | 588 us           |
    +----------------------------------+------------------+
    | ``ConversionTime.TIME_1_1_ms``   | 1.1 ms (Default) |
    +----------------------------------+------------------+
    | ``ConversionTime.TIME_2_116_ms`` | 2.116 ms         |
    +----------------------------------+------------------+
    | ``ConversionTime.TIME_4_156_ms`` | 4.156 ms         |
    +----------------------------------+------------------+
    | ``ConversionTime.TIME_8_244_ms`` | 8.244 ms         |
    +----------------------------------+------------------+

    """

    TIME_140_us = const(0x0)
    TIME_204_us = const(0x1)
    TIME_332_us = const(0x2)
    TIME_588_us = const(0x3)
    TIME_1_1_ms = const(0x4)
    TIME_2_116_ms = const(0x5)
    TIME_4_156_ms = const(0x6)
    TIME_8_244_ms = const(0x7)

    @staticmethod
    def get_seconds(time_enum: int) -> float:
        """Retrieve the time in seconds giving value read from register"""
        conv_dict = {
            0: 140e-6,
            1: 204e-6,
            2: 332e-6,
            3: 588e-6,
            4: 1.1e-3,
            5: 2.116e-3,
            6: 4.156e-3,
            7: 8.244e-3,
        }
        return conv_dict[time_enum]

class AveragingCount:
    """Options for ``averaging_count``

    +-------------------------------+------------------------------------+
    | ``AveragingCount``            | Number of measurements to average  |
    +===============================+====================================+
    | ``AveragingCount.COUNT_1``    | 1 (Default)                        |
    +-------------------------------+------------------------------------+
    | ``AveragingCount.COUNT_4``    | 4                                  |
    +-------------------------------+------------------------------------+
    | ``AveragingCount.COUNT_16``   | 16                                 |
    +-------------------------------+------------------------------------+
    | ``AveragingCount.COUNT_64``   | 64                                 |
    +-------------------------------+------------------------------------+
    | ``AveragingCount.COUNT_128``  | 128                                |
    +-------------------------------+------------------------------------+
    | ``AveragingCount.COUNT_256``  | 256                                |
    +-------------------------------+------------------------------------+
    | ``AveragingCount.COUNT_512``  | 512                                |
    +-------------------------------+------------------------------------+
    | ``AveragingCount.COUNT_1024`` | 1024                               |
    +-------------------------------+------------------------------------+

    """

    COUNT_1 = const(0x0)
    COUNT_4 = const(0x1)
    COUNT_16 = const(0x2)
    COUNT_64 = const(0x3)
    COUNT_128 = const(0x4)
    COUNT_256 = const(0x5)
    COUNT_512 = const(0x6)
    COUNT_1024 = const(0x7)

    @staticmethod
    def get_averaging_count(avg_count: int) -> float:
        """Retrieve the number of measurements giving value read from register"""
        conv_dict = {0: 1, 1: 4, 2: 16, 3: 64, 4: 128, 5: 256, 6: 512, 7: 1024}
        return conv_dict[avg_count]


# pylint: enable=too-few-public-methods

class INA260:

    REG_CONFIG = const(0x00)  # CONFIGURATION REGISTER (R/W)
    REG_CURRENT = const(0x01)  # SHUNT VOLTAGE REGISTER (R)
    REG_BUSVOLTAGE = const(0x02)  # BUS VOLTAGE REGISTER (R)
    REG_POWER = const(0x03)  # POWER REGISTER (R)
    REG_MASK_ENABLE = const(0x06)  # MASK ENABLE REGISTER (R/W)
    REG_ALERT_LIMIT = const(0x07)  # ALERT LIMIT REGISTER (R/W)
    REG_MFG_UID = const(0xFE)  # MANUFACTURER UNIQUE ID REGISTER (R)
    REG_DIE_UID = const(0xFF)  # DIE UNIQUE ID REGISTER (R)

    def __init__(self, i2c_bus: I2C, address: int = 0x40) -> None:
        self._i2c = i2c_bus
        self._address = address
        self._buf = bytearray(6)
        self.reset()
        #if not self.initialize():
        #    raise RuntimeError("Could not initialize")

    def reset(self):
        conf = self._i2c.readfrom_mem(self._address, self.REG_CONFIG, 2)
        #print("{:08b} {:08b}".format(conf[0], conf[1]))
    
    @property
    def current(self) -> float:
        """The current (between V+ and V-) in mA"""
        i = self._i2c.readfrom_mem(self._address, self.REG_CURRENT, 2)
        #print("i: {:08b} {:08b}".format(i[0], i[1]))
        return ustruct.unpack(">h", i)[0] * 0.00125
    
    @property
    def voltage(self) -> float:
        """The bus voltage in V"""
        v = self._i2c.readfrom_mem(self._address, self.REG_BUSVOLTAGE, 2)
        #print("v: {:08b} {:08b}".format(v[0], v[1]))
        return ustruct.unpack(">h", v)[0] * 0.00125
    
    @property
    def power(self) -> int:
        """The power being delivered to the load in mW"""
        p = self._i2c.readfrom_mem(self._address, self.REG_POWER, 2)
        #print("p: {:08b} {:08b}".format(p[0], p[1]))
        return ustruct.unpack(">h", p)[0] * 0.01


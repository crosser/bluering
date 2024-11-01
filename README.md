# BlueRing

A tool to communicate with some health sensor rings, such as colmi

Fresh reimplementation of what
[https://github.com/tahnok/colmi\_r02\_client/](https://github.com/tahnok/colmi_r02_client/)
does.

There is another project that supports it:
[https://codeberg.org/Freeyourgadget/Gadgetbridge/](https://codeberg.org/Freeyourgadget/Gadgetbridge/)

This command list comes form the project above:

```
CMD_SET_DATE_TIME	0x01
CMD_BATTERY		0x03
CMD_PHONE_NAME		0x04
CMD_POWER_OFF		0x08
CMD_PREFERENCES		0x0a
CMD_SYNC_HEART_RATE	0x15
CMD_AUTO_HR_PREF	0x16
CMD_GOALS		0x21
CMD_AUTO_SPO2_PREF	0x2c
CMD_PACKET_SIZE		0x2f
CMD_AUTO_STRESS_PREF	0x36
CMD_SYNC_STRESS		0x37
CMD_AUTO_HRV_PREF	0x38
CMD_SYNC_HRV		0x39
CMD_SYNC_ACTIVITY	0x43
CMD_FIND_DEVICE		0x50
CMD_MANUAL_HEART_RATE	0x69
CMD_NOTIFICATION	0x73

CMD_BIG_DATA_V2		0xbc
CMD_FACTORY_RESET	0xff
```

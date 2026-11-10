define Device/netgear_r6800
  $(Device/netgear_sercomm_nand)
  DEVICE_MODEL := R6800
  SERCOMM_HWNAME := R6950
  SERCOMM_HWID := BZV
  SERCOMM_HWVER := A001
  SERCOMM_SWVER := 0x0062
  IMAGE_SIZE := 40960k
  DEVICE_PACKAGES += kmod-mt7615-firmware
endef
TARGET_DEVICES += netgear_r6800

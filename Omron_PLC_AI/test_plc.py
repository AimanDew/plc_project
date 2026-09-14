import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from omron_plc import OmronPLC

print("=" * 60)
print("OMRON PLC TEST")
print("=" * 60)

plc = OmronPLC()

if not plc.connect():
    print("Failed to connect")
    sys.exit(1)

print("\n--- LIST TAGS ---")
tags = plc.list_tags()
print(f"Total tags: {len(tags)}")
for t in tags:
    print(f"  {t['name']:<25} {t['address']:<10} {t['type']:<6} {t['comment']}")

print("\n--- READ ALL TAGS ---")
all_tags = plc.read_all_tags()
for name, value in all_tags.items():
    print(f"  {name:<25} = {value}")

print("\n--- READ SINGLE TAGS ---")
print(f"  Emergency Stop: {plc.read_tag('Emergency Stop')}")
print(f"  Mode Selector:  {plc.read_tag('Mode Selector')}")
print(f"  Temp RTD1:      {plc.read_tag('Temp RTD1')}")
print(f"  TL Green:       {plc.read_tag('TL Green')}")

plc.disconnect()
print("\nDone.")
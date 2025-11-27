"""Check what shapes are saved in the database."""
from db import get_topology_shapes

shapes = get_topology_shapes()
print(f"\n{'='*80}")
print(f"Total shapes in database: {len(shapes)}")
print(f"{'='*80}\n")

for s in shapes:
    print(f"ID: {s['id']}")
    print(f"  Type: {s['type']}")
    print(f"  Position: X={s['x']}, Y={s['y']}")
    print(f"  Size: W={s.get('w')}, H={s.get('h')}")
    print(f"  Endpoints: X2={s.get('x2')}, Y2={s.get('y2')}")
    print(f"  Color: {s.get('color')}")
    print(f"  Fill Color: {s.get('fill_color')}")
    print(f"  Stroke Width: {s.get('stroke_width')}")
    print(f"  Text: {s.get('text')}")
    print()

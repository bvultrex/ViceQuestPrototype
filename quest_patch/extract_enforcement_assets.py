from pathlib import Path
import struct, sys, json
from PIL import Image

root=Path(sys.argv[1]).resolve()
vehicle_out=root/'assets/vehicles'
ui_out=root/'assets/ui/gta2'
vehicle_out.mkdir(parents=True,exist_ok=True)
ui_out.mkdir(parents=True,exist_ok=True)

VEHICLES={'agent_car':14,'armed_land_roamer':22,'land_roamer':30,'swat_van':52}

def chunks(data):
    result={}; pos=6
    while pos+8<=len(data):
        kind=data[pos:pos+4].decode('latin1'); size=struct.unpack_from('<I',data,pos+4)[0]
        result[kind]=(pos+8,size); pos+=8+size
    return result

def car_sprite_lookup(data,cari_offset,cari_size):
    lookup={}; cursor=0; relative_sprite=0
    while cursor<cari_size:
        record=cari_offset+cursor
        model=data[record]; sprite_count=data[record+1]; remap_count=data[record+4]
        lookup[model]=relative_sprite
        door_count_offset=record+14+remap_count
        door_count=data[door_count_offset]
        cursor=door_count_offset-cari_offset+1+door_count*2
        relative_sprite+=sprite_count
    return lookup

def sprite_tools(sty):
    data=sty.read_bytes(); t=chunks(data)
    spg,_=t['SPRG']; sprx,sprx_size=t['SPRX']; palx,_=t['PALX']; ppal,_=t['PPAL']; sprb,_=t['SPRB']; palb,_=t['PALB']
    sprite_counts=struct.unpack_from('<6H',data,sprb); palette_counts=struct.unpack_from('<8H',data,palb)
    sprite_bases=[]; run=0
    for n in sprite_counts:
        sprite_bases.append(run); run+=n
    palette_bases=[]; run=0
    for n in palette_counts:
        palette_bases.append(run); run+=n
    def rgba(physical,c,clear_index_one=False):
        idx=(physical//64)*64*256+(physical%64)+c*64
        v=struct.unpack_from('<I',data,ppal+idx*4)[0]
        return ((v>>16)&255,(v>>8)&255,v&255,0 if c==0 or (clear_index_one and c==1) else 255)
    def sprite(true_index,clear_index_one=False):
        pointer,w,h,_=struct.unpack_from('<IBBH',data,sprx+true_index*8)
        vp=palette_bases[1]+true_index
        physical=struct.unpack_from('<H',data,palx+vp*2)[0]
        image=Image.new('RGBA',(w,h),(0,0,0,0)); px=image.load()
        for y in range(h):
            row=spg+pointer+y*256
            for x in range(w):
                px[x,y]=rgba(physical,data[row+x],clear_index_one)
        return image
    return data,t,sprite,sprite_bases,sprx_size//8

wil=root/'source_gta2/wil.sty'
data,t,sprite,bases,_=sprite_tools(wil)
cari,cari_size=t['CARI']
lookup=car_sprite_lookup(data,cari,cari_size)
resolved={}
for name,model in VEHICLES.items():
    idx=lookup[model]; resolved[name]=idx
    sprite(idx).transpose(Image.Transpose.ROTATE_270).save(vehicle_out/f'{name}.png',optimize=True)

fstyle=root/'source_gta2/fstyle.sty'
_,_,fsprite,_,fcount=sprite_tools(fstyle)
for idx,name in [(5,'wanted_head_idle'),(6,'wanted_head_alert')]:
    if idx>=fcount:
        raise SystemExit(f'fstyle sprite {idx} missing')
    fsprite(idx).save(ui_out/f'{name}.png',optimize=True)

(ui_out/'enforcement_asset_manifest.json').write_text(json.dumps({
    'vehicles':VEHICLES,
    'resolved_car_sprites':resolved,
    'wanted_heads':{'idle':5,'alert':6}
},indent=2)+'\n',encoding='utf-8')
print('Extracted GTA2 SWAT/agent/military vehicle sprites and wanted-head HUD assets.')

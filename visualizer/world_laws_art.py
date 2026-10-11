"""Small vector scenery shared by the animated world-law illustration."""
from html import escape


def scenery(item, color):
    parts = []
    def path(d, fill, stroke=None):
        parts.append(f'<path d="{d}" fill="{fill}"'+(f' stroke="{stroke}" stroke-width="2"' if stroke else '')+'/>')
    def rect(x,y,w,h,c):
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{c}"/>')
    def block(x,y,w,h,c):
        rect(x,y,w,h,c)
        path(f'M{x},{y}l10,-6h{w}l-10,6Z', '#e3e8da')
        path(f'M{x+w},{y}l10,-6v{h}l-10,6Z', '#647b70')
    # Stepped earth strata converge into a suspended island.
    path('M-60,39L0,67L60,39L0,16Z', '#d5e0bc')
    path('M-60,39L0,67L60,39L48,60L0,82L-48,60Z', '#bb9864')
    path('M-48,60L0,82L48,60L33,82L0,103L-33,82Z', '#946b47')
    path('M-33,82L0,103L33,82L14,105L0,119L-14,105Z', '#694c37')
    path('M0,67L60,39L48,60L0,82Z', '#9c774f')
    path('M0,82L48,60L33,82L0,103Z', '#785437')
    for x,y in ((-43,55),(-28,73),(-11,91),(21,73)):
        rect(x,y,7,4,'#d1b481')
    path('M-47,34L-27,24L-8,31L-28,43Z', '#78a486')
    path('M12,39L31,30L47,38L29,47Z', '#e5ddbd')
    if item in ('A','B'):
        # Mountain ridges and a descending stream are part of the source pools.
        path('M-53,25L-53,8L-46,8L-46,-4L-38,-4L-38,-19L-30,-19L-30,-30L-22,-30L-22,-14L-13,-14L-13,3L-5,3L-5,27Z', '#789480')
        path('M-30,-19L-30,-30L-22,-30L-22,-14L-13,-14L-13,3L-21,3L-21,-5Z', '#a9bd9b')
        path('M-38,-19L-30,-30L-22,-14L-30,-14L-30,-19Z', '#f3f0da')
        path('M-21,20L-9,25L-9,32L2,37L2,45L14,51L14,77L7,81L7,56L-5,50L-5,41L-16,36L-16,29L-25,25Z', '#70b7b1')
        rect(9,58,3,19,'#d8eee0')
        # Conifer in discrete branches.
        rect(-45,18,5,17,'#795f41')
        path('M-53,22h21v-6h-4v-7h-4V1h-6v8h-4v7h-3Z', '#497e65')
        rect(-44,9,5,9,'#78a779')
    else:
        rect(-45,19,4,15,'#795f41')
        path('M-54,19v-8h5V3h14v8h5v8h-5v7h-14v-7Z', '#83a889')
        rect(-48,6,8,7,'#aec39c')
    # Each material has its own industrial vessel / archive / power equipment.
    if item in ('A','B'):
        block(0,0,29,32,'#a0b5a5')
        path('M0,0L10,-6H39L29,0Z', '#6c8274')
        path('M5,-2L11,-11L17,-6L23,-16L29,-8L34,-4L28,0Z', color)
        rect(5,16,17,9,'#425d53')
    elif item=='C':
        block(-11,-7,38,43,'#a6b9a9')
        rect(-5,0,25,26,'#395e54')
        rect(0,4,15,18,color)
        rect(3,5,4,15,'#f8dfa4')
        block(17,-31,9,19,'#789787')
        rect(-5,29,5,4,'#e6cf86')
    elif item=='W':
        block(-9,7,40,27,'#899e8e')
        for x in (-3,10,23):
            block(x,-17,8,30,'#b9c5ad')
            rect(x+1,-13,6,16,color)
        path('M-18,23v-9h9v8', 'none', '#647d6f')
    elif item=='D':
        block(-10,-12,36,47,'#8c9e99')
        for y in (-6,4,14):
            rect(-5,y,26,6,'#435b59')
            rect(-2,y+1,4,4,color)
        block(-21,25,19,7,'#c0b69a')
        rect(-18,20,6,5,color)
    else:
        block(-7,-9,33,43,'#a5b5a0')
        rect(0,-3,19,24,'#526d57')
        path('M10,-1L3,10H9L5,20L17,7H11L15,-1Z', color)
        block(-16,17,8,17,'#b7c495')
        rect(-15,20,5,7,color)
    # Small stones and flowers provide distributed material texture.
    rect(33,29,5,4,color); rect(38,34,4,3,'#6d9275')
    rect(-34,38,3,3,'#f0cd83'); rect(-29,41,3,3,'#e2ab94')
    return ''.join(parts)


def member(index):
    coat=['#699b86','#739caa','#a28aae'][index]
    rows=['...hhhh...','..hhhhhh..','..ssssss..','..sissis..','..ssmmss..','.swwccwws.','..wwccww..','..wwwwww..','...pppp...','...p..p...']
    palette={'h':'#796447','s':'#efd2b0','i':'#30483d','m':'#c68d79','w':'#f5f2dc','c':coat,'p':'#536c61'}
    return ''.join(f'<rect x="{col*5}" y="{row*5}" width="5" height="5" fill="{palette[p]}"/>' for row,line in enumerate(rows) for col,p in enumerate(line) if p in palette)

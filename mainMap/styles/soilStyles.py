"""
Colours of the soil map (physicalEnv.SoilArea), taken from the legend of
the BRO Bodemkaart 1:50 000 WMS (PDOK, style 'soilslope'):
https://service.pdok.nl/tno/bro-bodemkaart/wms/v1_0/legend/soilarea/soilslope.png

The legend colours each main soil unit (first_soilcode, stored as
SoilType.unitCode), not the full map code: 'Hn21/Hd21' and 'kHn21' are
drawn as Hn21. Keys are in legend order. Three names occur twice in the
legend, once per code (MOb72/ROb72, MOb75/ROb75, pMv81/pRv81); the first
row is the marine (M) code, the second the river (R) code.

Like the land-cover legend (mainMap/styles/landCoverStyles.py), the map style and its
legend are built per request from the units present in the database.
"""

SOIL_UNIT_COLORS = {
    'hVb': '#58207c',       # Koopveengronden op bosveen (of eutroof broekveen)
    'hVs': '#5820a7',       # Koopveengronden op veenmosveen
    'hVc': '#5820a7',       # Koopveengronden op zeggeveen, rietzeggeveen of (mesotroof) broekveen
    'hVr': '#5820a7',       # Koopveengronden op rietveen of zeggerietveen
    'hVd': '#5820a7',       # Koopveengronden op bagger, verslagen veen, gyttja of andere veensoorten
    'hVk': '#814ca7',       # Koopveengronden op (meestal niet-gerijpte) zavel of klei, beginnend ondieper dan 1.2 m
    'hVz': '#814ca7',       # Koopveengronden op zand, beginnend ondieper dan 1.2 m
    'hEV': '#320249',       # Aarveengronden
    'aVs': '#8120fe',       # Madeveengronden op veenmosveen
    'aVc': '#5820fe',       # Madeveengronden op zeggeveen, rietzeggeveen of broekveen
    'aVz': '#814cfe',       # Madeveengronden op zand zonder humuspodzol, beginnend ondieper dan 1.2 m
    'aVp': '#aa4cfe',       # Madeveengronden op zand met humuspodzol, beginnend ondieper dan 1.2 m
    'Vo': '#197ffe',        # Vlietveengronden
    'pVb': '#1920a7',       # Weideveengronden op bosveen (of eutroof broekveen)
    'pVs': '#1920fe',       # Weideveengronden op veenmosveen
    'pVc': '#1920fe',       # Weideveengronden op zeggeveen, rietzeggeveen of (mesotroof) broekveen
    'pVr': '#1920fe',       # Weideveengronden op rietveen of zeggerietveen
    'pVd': '#1920fe',       # Weideveengronden op bagger, verslagen veen, gyttja of andere veensoorten
    'pVk': '#324cfe',       # Weideveengronden op (meestal niet-gerijpte) zavel of klei, beginnend ondieper dan 1.2 m
    'pVz': '#324cfe',       # Weideveengronden op zand, beginnend ondieper dan 1.2 m
    'kVb': '#1920a7',       # Waardveengronden op bosveen (of eutroof broekveen)
    'kVs': '#1920fe',       # Waardveengronden op veenmosveen
    'kVc': '#1920fe',       # Waardveengronden op zeggeveen, rietzeggeveen of (mesotroof) broekveen
    'kVr': '#1920fe',       # Waardveengronden op rietveen of zeggerietveen
    'kVd': '#1920fe',       # Waardveengronden op bagger, verslagen veen, gyttja of andere veensoorten
    'kVk': '#324cfe',       # Waardveengronden op (meestal niet-gerijpte) zavel of klei, beginnend ondieper dan 1.2 m
    'kVz': '#324cfe',       # Waardveengronden op zand, beginnend ondieper dan 1.2 m
    'zVs': '#817ffe',       # Meerveengronden op veenmosveen
    'zVc': '#587ffe',       # Meerveengronden op zeggeveen, rietzeggeveen of broekveen
    'zVz': '#81aafe',       # Meerveengronden op zand zonder humuspodzol, beginnend ondieper dan 1.2 m
    'zVp': '#aaaafe',       # Meerveengronden op zand met humuspodzol, beginnend ondieper dan 1.2 m
    'Vb': '#1902a7',        # Vlierveengronden op bosveen (of eutroof broekveen)
    'Vs': '#1902fe',        # Vlierveengronden op veenmosveen
    'Vc': '#1902fe',        # Vlierveengronden op zeggeveen, rietzeggeveen of (mesotroof) broekveen
    'Vr': '#1902fe',        # Vlierveengronden op rietveen of zeggerietveen
    'Vd': '#1902fe',        # Vlierveengronden op bagger, verslagen veen, gyttja of andere veensoorten
    'Vk': '#3220fe',        # Vlierveengronden op (meestal niet-gerijpte) zavel of klei, beginnend ondieper dan 1.2 m
    'Vz': '#3220fe',        # Vlierveengronden op zand zonder humuspodzol, beginnend ondieper dan 1.2 m
    'Vp': '#3220fe',        # Vlierveengronden op zand met humuspodzol, beginnend ondieper dan 1.2 m
    'iVs': '#aa20fe',       # Veengronden met een veenkoloniaal dek op veenmosveen
    'iVc': '#584cfe',       # Veengronden met een veenkoloniaal dek op zeggeveen, rietzeggeveen of moerasbosveen
    'iVz': '#aa7ffe',       # Veengronden met een veenkoloniaal dek op zand zonder humuspodzol, beginnend ondieper dan 1.2 m
    'iVp': '#d37ffe',       # Veengronden met een veenkoloniaal dek op zand met humuspodzol, beginnend ondieper dan 1.2 m
    'kWp': '#584cd0',       # Moerige podzolgronden met een zavel- of een kleidek en een moerige tussenlaag
    'vWp': '#d320d0',       # Moerige podzolgronden met een moerige bovengrond
    'zWp': '#d37fd0',       # Moerige podzolgronden met een humushoudend zanddek en een moerige tussenlaag
    'iWp': '#d34cd0',       # Moerige podzolgronden met een veenkoloniaal dek en een moerige tussenlaag
    'Wo': '#197fa7',        # Moerige eerdgronden met een moerige bovengrond of moerige tussenlaag op niet-gerijpte zavel of klei
    'Wg': '#324ca7',        # Moerige eerdgronden met een moerige bovengrond of moerige tussenlaag op gerijpte zavel of klei
    'kWz': '#327fd0',       # Moerige eerdgronden met een zavel- of kleidek en een moerige tussenlaag op zand
    'zWz': '#aa7fd0',       # Moerige eerdgronden met een zanddek en een moerige tussenlaag op zand
    'uWz': '#aa7fd0',       # Moerige eerdgronden met een mineraal dek 5-8% lutum en een moerige tussenlaag op zand
    'vWz': '#aa20d0',       # Moerige eerdgronden met een moerige bovengrond op zand
    'iWz': '#aa4cd0',       # Moerige eerdgronden met een veenkoloniaal dek en een moerige tussenlaag op zand
    'Y21': '#fe7f49',       # Holtpodzolgronden; leemarm en zwak lemig fijn zand
    'Y23': '#d37f49',       # Holtpodzolgronden; lemig fijn zand
    'Y30': '#feaa49',       # Holtpodzolgronden; grof zand
    'Y23b': '#d3aa49',      # Horstpodzolgronden; lemig fijn zand
    'cY21': '#d37f49',      # Loopodzolgronden; leemarm en zwak lemig fijn zand
    'cY23': '#aa7f49',      # Loopodzolgronden; lemig fijn zand
    'cY30': '#d3aa49',      # Loopodzolgronden; grof zand
    'Hn21': '#fe7f7c',      # Veldpodzolgronden; leemarm en zwak lemig fijn zand
    'Hn23': '#d37f7c',      # Veldpodzolgronden; lemig fijn zand
    'Hn30': '#fe7fa7',      # Veldpodzolgronden; grof zand
    'cHn21': '#d37f7c',     # Laarpodzolgronden; leemarm en zwak lemig fijn zand
    'cHn23': '#aa7f7c',     # Laarpodzolgronden; lemig fijn zand
    'cHn30': '#d37fa7',     # Laarpodzolgronden; grof zand
    'Hd21': '#feaaa7',      # Haarpodzolgronden; leemarm en zwak lemig fijn zand
    'Hd23': '#d3aaa7',      # Haarpodzolgronden; lemig fijn zand
    'Hd30': '#feaad0',      # Haarpodzolgronden; grof zand
    'cHd21': '#d3aaa7',     # Kamppodzolgronden; leemarm en zwak lemig fijn zand
    'cHd23': '#aaaaa7',     # Kamppodzolgronden; lemig fijn zand
    'cHd30': '#d3aad0',     # Kamppodzolgronden; grof zand
    'BLn5': '#aa2000',      # Kuilbrikgronden; zandige leem
    'BLn6': '#aa0200',      # Kuilbrikgronden; siltige leem
    'BLh5': '#d32000',      # Daalbrikgronden; zandige leem
    'BLh6': '#d30200',      # Daalbrikgronden; siltige leem
    'BLd5': '#fe2000',      # Radebrikgronden; zandige leem
    'BLd6': '#fe0200',      # Radebrikgronden; siltige leem
    'BLb6': '#fe021e',      # Bergbrikgronden; siltige leem
    'BKh25': '#d34c1e',     # Daalbrikgronden; fijnzandige lichte zavel
    'BKh26': '#d34c1e',     # Daalbrikgronden; fijnzandige, siltige, lichte zavel
    'BKd25': '#fe4c1e',     # Radebrikgronden; fijnzandige lichte zavel
    'BKd26': '#fe4c1e',     # Radebrikgronden; fijnzandige, siltige, lichte zavel
    'BZd23': '#fe7f00',     # Rooibrikgronden; zwak en sterk lemig fijn zand
    'BZd24': '#fe4c00',     # Rooibrikgronden; zeer sterk lemig fijn zand
    'EZg21': '#817f7c',     # Lage enkeerdgronden; leemarm en zwak lemig fijn zand
    'EZg23': '#587f7c',     # Lage enkeerdgronden; lemig fijn zand
    'EZg30': '#817fa7',     # Lage enkeerdgronden; grof zand
    'bEZ21': '#810200',     # Hoge bruine enkeerdgronden; leemarm en zwak lemig fijn zand
    'bEZ23': '#580200',     # Hoge bruine enkeerdgronden; lemig fijn zand
    'bEZ30': '#58021e',     # Hoge bruine enkeerdgronden; grof zand
    'zEZ21': '#582000',     # Hoge zwarte enkeerdgronden; leemarm en zwak lemig fijn zand
    'zEZ23': '#322000',     # Hoge zwarte enkeerdgronden; lemig fijn zand
    'zEZ30': '#58201e',     # Hoge zwarte enkeerdgronden; grof zand
    'EZ50A': '#817f49',     # Kalkhoudende enkeerdgronden; matig fijn zand
    'EK76': '#324c49',      # Tuineerdgronden; zware zavel en klei, profielverloop 3, of 3 en 4, of 4
    'EK19': '#587f49',      # Tuineerdgronden; lichte zavel, profielverloop 5, of 5 en 2, of 2
    'EK79': '#587f49',      # Tuineerdgronden; zware zavel en klei, profielverloop 5, of 5 en 2, of 2
    'EL5': '#587f49',       # Tuineerdgronden; zandige leem
    'pZg21': '#d3fea7',     # Beekeerdgronden; leemarm en zwak lemig fijn zand
    'pZg23': '#aafea7',     # Beekeerdgronden; lemig fijn zand
    'pZg30': '#d3fed0',     # Beekeerdgronden; grof zand
    'pZn21': '#fed349',     # Gooreerdgronden; leemarm en zwak lemig fijn zand
    'pZn23': '#d3d349',     # Gooreerdgronden; lemig fijn zand
    'pZn30': '#fed37c',     # Gooreerdgronden; grof zand
    'tZd21': '#fefe00',     # Kanteerdgronden; leemarm en zwak lemig fijn zand
    'tZd23': '#fefe00',     # Kanteerdgronden; lemig fijn zand
    'tZd30': '#fefe00',     # Kanteerdgronden; grof zand
    'cZd21': '#aaaa00',     # Akkereerdgronden; leemarm en zwak lemig fijn zand
    'cZd23': '#aaaa00',     # Akkereerdgronden; lemig fijn zand
    'cZd30': '#aaaa00',     # Akkereerdgronden; grof zand
    'Zn21': '#fed349',      # Vlakvaaggronden; leemarm en zwak lemig fijn zand
    'Zn23': '#d3d349',      # Vlakvaaggronden; lemig fijn zand
    'Zn30': '#fed37c',      # Vlakvaaggronden; grof zand
    'Zd21': '#fefe00',      # Duinvaaggronden; leemarm en zwak lemig fijn zand
    'Zd23': '#fefe00',      # Duinvaaggronden; lemig fijn zand
    'Zd30': '#fefe00',      # Duinvaaggronden; grof zand
    'Zb21': '#fed300',      # Vorstvaaggronden; leemarm en zwak lemig fijn zand
    'Zb23': '#d3d300',      # Vorstvaaggronden; lemig fijn zand
    'Zb30': '#fed31e',      # Vorstvaaggronden; grof zand
    'pZg20A': '#fefe1e',    # Kalkhoudende beekeerdgronden; zeer fijn en matig fijn zand
    'Zn10A': '#d3d31e',     # Kalkhoudende vlakvaaggronden; uiterst fijn zand
    'Zn30A': '#fefe7c',     # Kalkhoudende vlakvaaggronden; grof zand
    'Zn40A': '#fefe1e',     # Kalkhoudende vlakvaaggronden; zeer fijn zand
    'Zn50A': '#fefe49',     # Kalkhoudende vlakvaaggronden; matig fijn zand
    'Zd20A': '#fefea7',     # Kalkhoudende duinvaaggronden; fijn zand
    'Zd30A': '#fefed0',     # Kalkhoudende duinvaaggronden; grof zand
    'Zb20A': '#d3fe00',     # Kalkhoudende vorstvaaggronden; fijn zand
    'Zb30A': '#d3fe00',     # Kalkhoudende vorstvaaggronden; grof zand
    'Sn13A': '#d3fe1e',     # Kalkhoudende vlakvaaggronden; zwak en sterk lemig, kleiig, uiterst fijn zand
    'Sn14A': '#d3fe1e',     # Kalkhoudende vlakvaaggronden; zeer sterk lemig, kleiig, uiterst fijn zand
    'MOo02': '#d3fefe',     # Slikvaaggronden; zand beginnend ondieper dan 0.8 m
    'MOo05': '#aafefe',     # Slikvaaggronden; geen zand beginnend ondieper dan 0.8 m
    'MOb12': '#aafed0',     # Gorsvaaggronden; lichte zavel; zand beginnend ondieper dan 0.8 m
    'MOb72': '#aafed0',     # Gorsvaaggronden; zware zavel en klei; zand beginnend ondieper dan 0.8 m
    'MOb15': '#81fed0',     # Gorsvaaggronden; lichte zavel; geen zand beginnend ondieper dan 0.8 m
    'MOb75': '#81fed0',     # Gorsvaaggronden; zware zavel en klei; geen zand beginnend ondieper dan 0.8 m
    'ROb72': '#aafed0',     # Gorsvaaggronden; zware zavel en klei; zand beginnend ondieper dan 0.8 m
    'ROb75': '#81fed0',     # Gorsvaaggronden; zware zavel en klei; geen zand beginnend ondieper dan 0.8 m
    'pMv51': '#327f7c',     # Liedeerdgronden; zavel, profielverloop 1
    'pMv81': '#194c49',     # Liedeerdgronden; klei, profielverloop 1
    'pMo50': '#81d3a7',     # Tochteerdgronden; zavel
    'pMo80': '#58d3a7',     # Tochteerdgronden; klei
    'pMn52A': '#d3fe49',    # Kalkrijke leek-/woudeerdgronden; zavel, profielverloop 2
    'pMn82A': '#aafe49',    # Kalkrijke leek-/woudeerdgronden; klei, profielverloop 2
    'pMn55A': '#58fe49',    # Kalkrijke leek-/woudeerdgronden; zavel, profielverloop 5
    'pMn85A': '#32fe49',    # Kalkrijke leek-/woudeerdgronden; klei, profielverloop 5
    'pMn52C': '#d3d37c',    # Kalkarme leek-/woudeerdgronden; zavel, profielverloop 2
    'pMn82C': '#aad37c',    # Kalkarme leek-/woudeerdgronden; klei, profielverloop 2
    'pMn85C': '#32d349',    # Kalkarme leek-/woudeerdgronden; klei, profielverloop 5
    'pMn56C': '#58d37c',    # Kalkarme leek-/woudeerdgronden; zavel, profielverloop 3, of 3 en 4, of 4
    'pMn86C': '#32d37c',    # Kalkarme leek-/woudeerdgronden; klei, profielverloop 3, of 3 en 4 of 4
    'pMn55C': '#58d349',    # Kalkarme leek-/woudeerdgronden; zavel, profielverloop 5
    'Mv51A': '#58aaa7',     # Kalkrijke drechtvaaggronden; zavel, profielverloop 1
    'Mv81A': '#32aaa7',     # Kalkrijke drechtvaaggronden; klei, profielverloop 1
    'Mv61C': '#327f7c',     # Kalkarme drechtvaaggronden; zavel en lichte klei, profielverloop 1
    'Mv41C': '#194c49',     # Kalkarme drechtvaaggronden; zware klei, profielverloop 1
    'Mo10A': '#81fea7',     # Kalkrijke nesvaaggronden; lichte zavel
    'Mo20A': '#81fea7',     # Kalkrijke nesvaaggronden; zware zavel
    'Mo80A': '#58fea7',     # Kalkrijke nesvaaggronden; klei
    'Mo50C': '#81d3a7',     # Kalkarme nesvaaggronden; zavel
    'Mo80C': '#58d3a7',     # Kalkarme nesvaaggronden; klei
    'Mn12A': '#d3fe49',     # Kalkrijke poldervaaggronden; lichte zavel, profielverloop 2
    'Mn22A': '#d3fe49',     # Kalkrijke poldervaaggronden; zware zavel, profielverloop 2
    'Mn82A': '#aafe49',     # Kalkrijke poldervaaggronden; klei, profielverloop 2
    'Mn56A': '#58fe7c',     # Kalkrijke poldervaaggronden; zavel, profielverloop 3, of 3 en 4 of 4
    'Mn86A': '#32fe7c',     # Kalkrijke poldervaaggronden; klei, profielverloop 3, of 3 en 4, of 4
    'Mn15A': '#81fe49',     # Kalkrijke poldervaaggronden; lichte zavel, profielverloop 5
    'Mn25A': '#58fe49',     # Kalkrijke poldervaaggronden; zware zavel, profielverloop 5
    'Mn35A': '#32fe49',     # Kalkrijke poldervaaggronden; lichte klei, profielverloop 5
    'Mn45A': '#19fe49',     # Kalkrijke poldervaaggronden; zware klei, profielverloop 5
    'Mn52C': '#d3d37c',     # Kalkarme poldervaaggronden; zavel, profielverloop 2
    'Mn82C': '#aad37c',     # Kalkarme poldervaaggronden; klei, profielverloop 2
    'Mn56C': '#58d37c',     # Kalkarme poldervaaggronden; zavel, profielverloop 3, of 3 en 4, of 4
    'Mn86C': '#32d37c',     # Kalkarme poldervaaggronden; klei, profielverloop 3, of 3 en 4, of 4
    'Mn15C': '#81d349',     # Kalkarme poldervaaggronden; lichte zavel, profielverloop 5
    'Mn25C': '#58d349',     # Kalkarme poldervaaggronden; zware zavel, profielverloop 5
    'Mn85C': '#32d349',     # Kalkarme poldervaaggronden; klei, profielverloop 5
    'gMn52C': '#d3aa7c',    # Knippige poldervaaggronden; zavel, profielverloop 2
    'gMn82C': '#aaaa7c',    # Knippige poldervaaggronden; klei, profielverloop 2
    'gMn53C': '#32aa49',    # Knippige poldervaaggronden; zavel, profielverloop 3
    'gMn58C': '#32aa49',    # Knippige poldervaaggronden; zavel, profielverloop 4, of 4 en 3
    'gMn83C': '#19aa49',    # Knippige poldervaaggronden; klei, profielverloop 3
    'gMn88C': '#19aa49',    # Knippige poldervaaggronden; klei, profielverloop 4, of 4 en 3
    'gMn15C': '#aaaa49',    # Knippige poldervaaggronden; lichte zavel, profielverloop 5
    'gMn25C': '#81aa49',    # Knippige poldervaaggronden; zware zavel, profielverloop 5
    'gMn85C': '#58aa49',    # Knippige poldervaaggronden; klei, profielverloop 5
    'kMn63C': '#327f49',    # Knippoldervaaggronden; zavel en lichte klei, profielverloop 3
    'kMn68C': '#327f49',    # Knippoldervaaggronden; zavel en lichte klei, profielverloop 4, of 4 en 3
    'kMn43C': '#197f49',    # Knippoldervaaggronden; zware klei, profielverloop 3
    'kMn48C': '#197f49',    # Knippoldervaaggronden; zware klei, profielverloop 4, of 4 en 3
    'pRv81': '#19201e',     # Liedeerdgronden; klei, profielverloop 1
    'pRn56': '#32aa00',     # Leek-/woudeerdgronden; zavel, profielverloop 3, of 3 en 4, of 4
    'pRn86': '#19aa00',     # Leek-/woudeerdgronden; klei, profielverloop 3, of 3 en 4, of 4
    'pRn59': '#58d300',     # Leek-/woudeerdgronden; zavel, profielverloop 5, of 5 en 2, of 2
    'pRn89': '#32d300',     # Leek-/woudeerdgronden; klei, profielverloop 5, of 5 en 2, of 2
    'Rv01A': '#194c1e',     # Kalkhoudende drechtvaaggronden; profielverloop 1
    'Rv01C': '#19201e',     # Kalkloze drechtvaaggronden; profielverloop 1
    'Ro60A': '#19fe1e',     # Kalkhoudende nesvaaggronden; zavel en lichte klei
    'Ro40A': '#19fe1e',     # Kalkhoudende nesvaaggronden; zware klei
    'Ro60C': '#19aa1e',     # Kalkloze nesvaaggronden; zavel en lichte klei
    'Ro40C': '#19aa1e',     # Kalkloze nesvaaggronden; zware klei
    'Rn52A': '#aafe00',     # Kalkhoudende poldervaaggronden; zavel, profielverloop 2
    'Rn82A': '#aafe1e',     # Kalkhoudende poldervaaggronden; klei, profielverloop 2
    'Rn66A': '#19fe00',     # Kalkhoudende poldervaaggronden; zavel en lichte klei, profielverloop 3, of 3 en 4, of 4
    'Rn46A': '#19fe00',     # Kalkhoudende poldervaaggronden; zware klei, profielverloop 3, of 3 en 4 , of 4
    'Rn15A': '#81fe00',     # Kalkhoudende poldervaaggronden; lichte zavel, profielverloop 5
    'Rn95A': '#58fe00',     # Kalkhoudende poldervaaggronden; zware zavel en lichte klei, profielverloop 5
    'Rn45A': '#32fe00',     # Kalkhoudende poldervaaggronden; zware klei, profielverloop 5
    'Rn62C': '#aad31e',     # Kalkloze poldervaaggronden; zavel en lichte klei, profielverloop 2
    'Rn42C': '#aad31e',     # Kalkloze poldervaaggronden; zware klei, profielverloop 2
    'Rn14C': '#58aa00',     # Kalkloze poldervaaggronden; lichte zavel, profielverloop 4
    'Rn67C': '#32aa00',     # Kalkloze poldervaaggronden; zavel en lichte klei, profielverloop 3, of 3 en 4
    'Rn94C': '#32aa00',     # Kalkloze poldervaaggronden; zware zavel en lichte klei, profielverloop 4
    'Rn47C': '#19aa00',     # Kalkloze poldervaaggronden; zware klei, profielverloop 3, of 3 en 4
    'Rn95C': '#58d300',     # Kalkloze poldervaaggronden; zware zavel en lichte klei, profielverloop 5
    'Rn45C': '#32d300',     # Kalkloze poldervaaggronden; zware klei, profielverloop 5
    'Rn44C': '#197f1e',     # Kalkloze poldervaaggronden; zware klei, profielverloop 4
    'bRn46C': '#197f1e',    # Kalkloze poldervaaggronden (bruine komgrond); zware klei, profielverloop 3, of 3 en 4, of 4
    'Rn15C': '#81d300',     # Kalkloze poldervaaggronden; lichte zavel, profielverloop 5
    'Rd10A': '#81fe1e',     # Kalkhoudende ooivaaggronden; lichte zavel
    'Rd90A': '#58fe1e',     # Kalkhoudende ooivaaggronden; zware zavel en lichte klei
    'Rd10C': '#81d31e',     # Kalkloze ooivaaggronden; lichte zavel
    'Rd90C': '#58d31e',     # Kalkloze ooivaaggronden; zware zavel en lichte klei
    'pKRn1': '#81aa00',     # Leek-/woudeerdgronden; lichte zavel
    'pKRn2': '#587f00',     # Leek-/woudeerdgronden; zware zavel
    'KRn1': '#81aa00',      # Poldervaaggronden; lichte zavel
    'KRn2': '#587f00',      # Poldervaaggronden; zware zavel
    'KRn8': '#324c00',      # Poldervaaggronden; klei
    'KRd1': '#aaaa00',      # Ooivaaggronden, lichte zavel
    'KRd7': '#817f00',      # Ooivaaggronden; zware zavel en klei
    'pLn5': '#aa2049',      # Leek-/woudeerdgronden; zandige leem; colluvium in dal
    'Ln5': '#aa2049',       # Poldervaaggronden; zandige leem in situ
    'Ln6': '#aa2049',       # Poldervaaggronden; siltige leem in situ
    'Lnd5': '#aa2049',      # Poldervaaggronden; zandige leem; colluvium in dal
    'Lnd6': '#aa2049',      # Poldervaaggronden; siltige leem; colluvium in dal
    'Lnh6': '#aa2049',      # Poldervaaggronden; siltige leem; colluvium in hellingvoet of uitspoelingswaaier
    'Lh5': '#d32049',       # Ooivaaggronden met roest beginnend tussen 0.5 en 0.8 m; zandige leem in situ
    'Lh6': '#d32049',       # Ooivaaggronden met roest beginnend tussen 0.5 en 0.8 m; siltige leem in situ
    'Ld5': '#fe2049',       # Ooivaaggronden met roest beginnend dieper dan 0.8 m; zandige leem in situ
    'Ld6': '#fe2049',       # Ooivaaggronden met roest beginnend dieper dan 0.8 m; siltige leem in situ
    'Ldd5': '#fe2049',      # Ooivaaggronden met roest beginnend dieper dan 0.8 m; zandige leem; colluvium in dal
    'Ldd6': '#fe2049',      # Ooivaaggronden met roest beginnend dieper dan 0.8 m; siltige leem; colluvium in dal
    'Ldh5': '#fe2049',      # Ooivaaggronden met roest beginnend dieper dan 0.8 m; zandige leem; colluvium in hellingvoet of uitspoelingswaaier
    'Ldh6': '#fe2049',      # Ooivaaggronden met roest beginnend dieper dan 0.8 m; siltige leem; colluvium in hellingvoet of uitspoelingswaaier
    'MA': '#19d3d0',        # Mariene afzettingen ouder dan pleistoceen; glauconietklei
    'MK': '#32d3d0',        # Mariene afzettingen ouder dan pleistoceen; zavel en klei
    'MZk': '#32fed0',       # Mariene afzettingen ouder dan pleistoceen; fijn zand en zavel
    'MZz': '#32fed0',       # Mariene afzettingen ouder dan pleistoceen; fijn zand
    'KT': '#19d3a7',        # Overige kleigronden
    'FG': '#19d37c',        # Fluviatiele afzettingen ouder dan laat-pleistoceen; grind en grof zand
    'FK': '#19aa7c',        # Fluviatiele afzettingen ouder dan laat-pleistoceen; zavel en klei
    'KM': '#587f1e',        # Ondiep kalksteen
    'KK': '#81aa1e',        # Kleefaarde
    'KS': '#32aa1e',        # Vuursteen eluvium
    'KX': '#fe0249',        # Zeer ondiepe keileem, potklei, enz
    'AAK': '#587fa7',       # Afgegraven kleigronden
    'AAP': '#324ca7',       # Aangemaakte petgaten
    'ABk': '#58aa1e',       # Kleiige beekdalgronden
    'ABl': '#327f7c',       # Lössige beekdalgronden
    'ABz': '#817f7c',       # Zandige beekdalgronden
    'ABv': '#587f7c',       # Venige beekdalgronden
    'AEk9': '#32fe49',      # Geëgaliseerde en verwerkte zeekleigronden zonder veen binnen 1.2 m; zw. zavel en l. klei
    'AEm5': '#58aa49',      # Geëgaliseerde en verwerkte zeekleigronden met plaats. veen binnen 1.2 m; zavel
    'AEm8': '#194c49',      # Geëgaliseerde en verwerkte zeekleigronden met plaats. veen binnen 1.2 m; klei
    'AEm9': '#327f49',      # Geëgaliseerde en verwerkte zeekleigronden met plaats. veen binnen 1.2 m; zw. zavel en l. klei
    'AEm9A': '#197f7c',     # Geëgaliseerde en verwerkte zeekleigronden met plaats. veen binnen 1.2 m of met niet-ger. ondergrond; zw. zavel en l. klei
    'AEp6A': '#58fe49',     # Geëgaliseerde en verwerkte zeekleigronden (eerd- en vaaggronden met ger. ondergrond); zavel en l. klei, kalkrijk
    'AEp7A': '#32fe1e',     # Geëgaliseerde en verwerkte zeekleigronden (eerd- en vaaggronden met ger. ondergrond); zw. zavel en klei, kalkrijk
    'AFk': '#32207c',       # Roodoornige kleiige Vechtdalgronden
    'AFz': '#584c7c',       # Roodoornige zandige Vechtdalgronden
    'AGm9C': '#324c49',     # Hollebollige, gemoerde zeekleigronden; zw. zavel en l. klei
    'AHa': '#19d3d0',       # Glauconiethellinggronden
    'AHc': '#d3207c',       # Löss-, terras- en kalksteenhellinggronden
    'AHk': '#d3aa1e',       # Kalksteenhellinggronden
    'AHl': '#fe207c',       # Löss- en terrashellinggronden
    'AHs': '#32aa1e',       # Vuursteenhellinggronden
    'AHt': '#d34c49',       # Terrashellinggronden
    'AHv': '#8120a7',       # Terras-, tertiair-, kalksteen- en veenhellinggronden
    'AHz': '#d3d300',       # Löss-, tertiair- en terrashellinggronden
    'AK': '#81aad0',        # Kreekbeddingen
    'ALu': '#32fe1e',       # Linge-uiterwaardgronden
    'AM': '#aa7f00',        # Mengelgronden
    'AMm': '#81d300',       # Gronden in oude maasmeanders
    'AD': '#aafe00',        # Duin- en kweldergronden
    'AO': '#58d349',        # Overslaggronden
    'AP': '#324cfe',        # Petgaten
    'AR': '#817f00',        # Roergronden
    'AS': '#fefe00',        # Stuifzandgronden
    'AVk': '#584ca7',       # Veenafbraakgebied
    'AVo': '#3220fe',       # Veen in ontginning
    'AWg': '#32d349',       # Warmoezerijgronden (gerijpt)
    'AWv': '#1920fe',       # Warmoezerijgronden (veen)
    'AZ1': '#fe7f00',       # Strandwalgronden
    'AZW0A': '#d3fe7c',     # Wieringermeergronden; zand, kalkrijk
    'AZW1A': '#aafe7c',     # Wieringermeergronden; zand en lichte zavel, kalkrijk
    'AZW5A': '#32fe7c',     # Wieringermeergronden; zand en zavel, kalkrijk
    'AZW6A': '#19fe49',     # Wieringermeergronden; zavel en klei, kalkrijk
    'AZW7A': '#19fe7c',     # Wieringermeergronden; zware zavel en klei, kalkrijk
    'AZW8A': '#19fea7',     # Wieringermeergronden; klei, kalkrijk
    'Zd20Ab': '#fefea7',    # Kalkhoudende duinvaaggronden; fijn zand, gedeeltelijk ontkalkt
    'Zn30Ab': '#fefe7c',    # Kalkhoudende vlakvaaggronden; grof zand, gedeeltelijk ontkalkt
    'Zn50Ab': '#fefe49',    # Kalkhoudende vlakvaaggronden; matig fijn zand, gedeeltelijk ontkalkt
    'uVz': '#324cfe',       # Meerveengronden met een mineraal dek 5-8 % lutum op zand zonder humuspodzol, beginnend ondieper dan 1.2 m
}
# Units missing from SOIL_UNIT_COLORS (a later map edition) and soil types
# imported before SoilType.unitCode existed.
SOIL_UNKNOWN_COLOR = '#bdbdbd'
SOIL_OUTLINE_COLOR = '#5d4037'


def build_soil_style_and_legend():
    """
    (style_layers, legend) for physicalEnv.SoilArea: a `match` on the
    soil_type__unitCode property (POPUP_RELATED_FIELDS in mainMap/views.py
    puts it on the GeoJSON) and a legend entry per unit present, in legend
    order.
    """
    from physicalEnv.models import SoilType

    units = dict(
        SoilType.objects.filter(areas__isnull=False, unitCode__isnull=False)
        .values_list('unitCode', 'unitName').distinct()
    )
    present = [code for code in SOIL_UNIT_COLORS if code in units]
    fill = (
        ['match', ['get', 'soil_type__unitCode'],
         *[v for code in present for v in (code, SOIL_UNIT_COLORS[code])],
         SOIL_UNKNOWN_COLOR]
        if present else SOIL_UNKNOWN_COLOR
    )
    style_layers = [
        {'type': 'fill', 'paint': {'fill-color': fill, 'fill-opacity': 0.6}},
        {'type': 'line', 'paint': {'line-color': fill, 'line-width': 0.3}},
    ]
    legend = [{'label': f'{code} {units[code]}', 'color': SOIL_UNIT_COLORS[code]} for code in present]
    if set(units) - set(present):
        legend.append({'label': 'Other soil units', 'color': SOIL_UNKNOWN_COLOR})
    return style_layers, legend

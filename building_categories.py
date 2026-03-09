# building_categories.py

import matplotlib.colors as mcolors

# Density factors - high density is lighter
DENSITY_FACTORS = {
    'low': 0.90,  # Darker
    'medium': 1.0,  # Made medium darker than before
    'high': 1.15  # Lighter
}

BUILDING_CATEGORIES = {
    'budynki zabytkowe i kulturalne': {
        'base_color': '#ff039e',  # Keeping your pink for landmarks
        'density': False,
        'description': 'Zabytki i kultura'
    },
    'budynki sakralne': {
        'base_color': '#ff039e',  # Same as landmarks
        'density': False,
        'description': 'Sakralne'
    },
    'budynki mieszkalne': {
        'base_color': '#00A000',  # Keeping your bright green for residential
        'density': True,
        'description': 'Mieszkalne'
    },
    'budynki produkcyjne, usługowe i gospodarcze dla rolnictwa': {
        # 'base_color': '#8B4513',  # Slightly darker and more brownish for agricultural
        'base_color': '#6e5d0c',
        'density': False,
        'description': 'Rolnicze'
    },
    'budynki handlowo-usługowe': {
        'base_color': '#057ffa',  # Keeping your darker blue for commerce
        'density': True,
        'description': 'Handlowo-usługowe'
    },
    'budynki przemysłowe i magazynowe': {
        'base_color': '#998202',
        # 'base_color': '#8f7701',
        # 'base_color': '#997700',  # Keeping your industrial color for combined industry/storage
        'density': False,
        'description': 'Przemysłowe i magazynowe'
    },
    'budynki oświaty i nauki': {
        'base_color': '#f56b26',  # Keeping your orange for education
        'density': False,
        'description': 'Oświata i nauka'
    },
    'budynki sportowe i rozrywkowe': {
        'base_color': '#94d194',  # Light celadon green for sports & entertainment
        'density': False,
        'description': 'Sport i rozrywka'
    },
    'budynki transportu': {
        'base_color': '#fffc3b',  # Bright blue for transport
        'density': False,
        'description': 'Transport'
    },
    'budynki urzędów i administracji publicznej': {
        'base_color': '#b359c9',  # Royal purple for government/administration
        'density': False,
        'description': 'Administracja publiczna'
    },
    'budynki biurowe': {
        'base_color': '#00e7eb',  # Keeping your orchid for commercial offices
        'density': True,
        'description': 'Biurowe'
    },
    'budynki szpitali i inne budynki opieki zdrowotnej': {
        'base_color': '#f00800',  # Keeping your red for healthcare
        'density': False,
        'description': 'Ochrona zdrowia'
    },
    'pozostałe budynki niemieszkalne': {
        'base_color': '#4D4D4D',  # Keeping your dark gray for others
        'density': False,
        'description': 'Pozostałe'
    }
}
# BDOT10k categories with adjusted colors
# Updated colors and categories


FUNCTION_TO_CATEGORY = {
    # Historic and Cultural Landmarks (budynki zabytkowe i kulturalne)
    'muzeum': 'budynki zabytkowe i kulturalne',
    'teatr': 'budynki zabytkowe i kulturalne',
    'opera': 'budynki zabytkowe i kulturalne',
    'filharmonia': 'budynki zabytkowe i kulturalne',
    'rezydencja prezydencka': 'budynki zabytkowe i kulturalne',
    'rezydencja ambasadora': 'budynki zabytkowe i kulturalne',
    'rezydencja biskupia': 'budynki zabytkowe i kulturalne',
    'zabytek niepełniący żadnej funkcji użytkowej': 'budynki zabytkowe i kulturalne',
    'galeria sztuki': 'budynki zabytkowe i kulturalne',
    'obserwatorium lub planetarium': 'budynki zabytkowe i kulturalne',
    'budynek ogrodu zoologicznego lub botanicznego': 'budynki zabytkowe i kulturalne',

    # Religious Buildings (budynki sakralne)
    'kościół': 'budynki sakralne',
    'cerkiew': 'budynki sakralne',
    'meczet': 'budynki sakralne',
    'synagoga': 'budynki sakralne',
    'kaplica': 'budynki sakralne',
    'klasztor': 'budynki sakralne',
    'dom zakonny': 'budynki sakralne',
    'kuria metropolitalna': 'budynki sakralne',
    'dom parafialny': 'budynki sakralne',
    'dom rekolekcyjny': 'budynki sakralne',
    'dzwonnica': 'budynki sakralne',
    'inny budynek kultu religijnego': 'budynki sakralne',

    # Residential buildings (budynki mieszkalne)
    'budynek jednorodzinny': 'budynki mieszkalne',
    'budynek wielorodzinny': 'budynki mieszkalne',
    'dom letniskowy': 'budynki mieszkalne',
    'dom studencki': 'budynki mieszkalne',
    'internat lub bursa szkolna': 'budynki mieszkalne',
    'hotel robotniczy': 'budynki mieszkalne',

    # Agricultural (budynki produkcyjne, usługowe i gospodarcze dla rolnictwa)
    'budynek gospodarczy': 'budynki produkcyjne, usługowe i gospodarcze dla rolnictwa',
    'budynek produkcyjny zwierząt hodowlanych': 'budynki produkcyjne, usługowe i gospodarcze dla rolnictwa',
    'szklarnia lub cieplarnia': 'budynki produkcyjne, usługowe i gospodarcze dla rolnictwa',
    'stajnia': 'budynki produkcyjne, usługowe i gospodarcze dla rolnictwa',
    'leśniczówka': 'budynki produkcyjne, usługowe i gospodarcze dla rolnictwa',
    'bacówka': 'budynki produkcyjne, usługowe i gospodarcze dla rolnictwa',
    'pawilon ogrodowy lub oranżeria': 'budynki produkcyjne, usługowe i gospodarcze dla rolnictwa',
    'schronisko dla zwierząt': 'budynki produkcyjne, usługowe i gospodarcze dla rolnictwa',
    'ujeżdżalnia': 'budynki produkcyjne, usługowe i gospodarcze dla rolnictwa',

    # Commercial (budynki handlowo-usługowe)
    'centrum handlowe': 'budynki handlowo-usługowe',
    'obiekt handlowo-usługowy': 'budynki handlowo-usługowe',
    'dom towarowy lub handlowy': 'budynki handlowo-usługowe',
    'hipermarket lub supermarket': 'budynki handlowo-usługowe',
    'restauracja': 'budynki handlowo-usługowe',
    'apteka': 'budynki handlowo-usługowe',
    'bank': 'budynki handlowo-usługowe',
    'hala targowa': 'budynki handlowo-usługowe',
    'kasyno': 'budynki handlowo-usługowe',
    'myjnia samochodowa': 'budynki handlowo-usługowe',
    'stacja obsługi pojazdów': 'budynki handlowo-usługowe',
    'stacja paliw': 'budynki handlowo-usługowe',
    'dom weselny': 'budynki handlowo-usługowe',
    'hotel': 'budynki handlowo-usługowe',
    'motel': 'budynki handlowo-usługowe',
    'pensjonat': 'budynki handlowo-usługowe',
    'domek kempingowy': 'budynki handlowo-usługowe',
    'schronisko turystyczne': 'budynki handlowo-usługowe',
    'dom wypoczynkowy': 'budynki handlowo-usługowe',
    'zajazd': 'budynki handlowo-usługowe',
    'ośrodek szkoleniowo-wypoczynkowy': 'budynki handlowo-usługowe',

    # Industrial & Storage (merged category - budynki przemysłowe i magazynowe)
    'produkcyjny': 'budynki przemysłowe i magazynowe',
    'elektrociepłownia': 'budynki przemysłowe i magazynowe',
    'elektrownia': 'budynki przemysłowe i magazynowe',
    'rafineria': 'budynki przemysłowe i magazynowe',
    'warsztat remontowo-naprawczy': 'budynki przemysłowe i magazynowe',
    'młyn': 'budynki przemysłowe i magazynowe',
    'wiatrak': 'budynki przemysłowe i magazynowe',
    'chłodnia': 'budynki przemysłowe i magazynowe',
    'kotłownia': 'budynki przemysłowe i magazynowe',
    'stacja transformatorowa': 'budynki przemysłowe i magazynowe',
    'spalarnia śmieci': 'budynki przemysłowe i magazynowe',
    'magazyn': 'budynki przemysłowe i magazynowe',
    'silos': 'budynki przemysłowe i magazynowe',
    'elewator': 'budynki przemysłowe i magazynowe',
    'zbiornik na ciecz': 'budynki przemysłowe i magazynowe',
    'zbiornik na gaz': 'budynki przemysłowe i magazynowe',
    'stacja gazowa': 'budynki przemysłowe i magazynowe',
    'stacja pomp': 'budynki przemysłowe i magazynowe',
    'budynek spedycji': 'budynki przemysłowe i magazynowe',
    'hangar': 'budynki przemysłowe i magazynowe',
    'lokomotywownia lub wagonownia': 'budynki przemysłowe i magazynowe',

    # Education (budynki oświaty i nauki) - Separated from sports
    'szkoła podstawowa': 'budynki oświaty i nauki',
    'szkoła ponadpodstawowa': 'budynki oświaty i nauki',
    'szkoła wyższa': 'budynki oświaty i nauki',
    'biblioteka': 'budynki oświaty i nauki',
    'dom kultury': 'budynki oświaty i nauki',
    'przedszkole': 'budynki oświaty i nauki',
    'inna placówka edukacyjna': 'budynki oświaty i nauki',
    'placówka badawcza': 'budynki oświaty i nauki',
    'centrum konferencyjne': 'budynki oświaty i nauki',
    'hala wystawowa': 'budynki oświaty i nauki',

    # Sports and Entertainment (budynki sportowe i rozrywkowe) - NEW CATEGORY
    'hala sportowa': 'budynki sportowe i rozrywkowe',
    'sala gimnastyczna': 'budynki sportowe i rozrywkowe',
    'basen kąpielowy': 'budynki sportowe i rozrywkowe',
    'korty tenisowe': 'budynki sportowe i rozrywkowe',
    'sztuczne lodowisko': 'budynki sportowe i rozrywkowe',
    'klub sportowy': 'budynki sportowe i rozrywkowe',
    'strzelnica': 'budynki sportowe i rozrywkowe',
    'halowy tor gokartowy': 'budynki sportowe i rozrywkowe',
    'kręgielnia': 'budynki sportowe i rozrywkowe',
    'klub, dyskoteka': 'budynki sportowe i rozrywkowe',
    'kino': 'budynki sportowe i rozrywkowe',
    'hala widowiskowa': 'budynki sportowe i rozrywkowe',

    # Transport (only public transport facilities)
    'dworzec kolejowy': 'budynki transportu',
    'dworzec autobusowy': 'budynki transportu',
    'dworzec lotniczy': 'budynki transportu',
    'terminal portowy': 'budynki transportu',
    'stacja kolejki górskiej lub wyciągu krzesełkowego': 'budynki transportu',
    'kapitanat lub bosmanat portu': 'budynki transportu',

    # Government/Public Offices (budynki urzędów i administracji publicznej) - NEW CATEGORY
    'ministerstwo': 'budynki urzędów i administracji publicznej',
    'sąd': 'budynki urzędów i administracji publicznej',
    'urząd miasta': 'budynki urzędów i administracji publicznej',
    'urząd gminy': 'budynki urzędów i administracji publicznej',
    'urząd wojewódzki': 'budynki urzędów i administracji publicznej',
    'urząd marszałkowski': 'budynki urzędów i administracji publicznej',
    'starostwo powiatowe': 'budynki urzędów i administracji publicznej',
    'placówka dyplomatyczna lub konsularna': 'budynki urzędów i administracji publicznej',
    'inny urząd administracji publicznej': 'budynki urzędów i administracji publicznej',
    'urząd miasta i gminy': 'budynki urzędów i administracji publicznej',
    'urząd celny': 'budynki urzędów i administracji publicznej',
    'prokuratura': 'budynki urzędów i administracji publicznej',
    'policja': 'budynki urzędów i administracji publicznej',
    'straż pożarna': 'budynki urzędów i administracji publicznej',
    'straż graniczna': 'budynki urzędów i administracji publicznej',
    'placówka operatora pocztowego': 'budynki urzędów i administracji publicznej',
    'zakład karny lub poprawczy': 'budynki urzędów i administracji publicznej',
    'zakład poprawczy': 'budynki urzędów i administracji publicznej',
    'schronisko dla nieletnich': 'budynki urzędów i administracji publicznej',
    'koszary': 'budynki urzędów i administracji publicznej',
    'zabudowania koszarowe': 'budynki urzędów i administracji publicznej',
    'areszt śledczy': 'budynki urzędów i administracji publicznej',
    'zakład karny': 'budynki urzędów i administracji publicznej',

    # Office (budynki biurowe) - Now just for commercial offices
    'siedziba firmy lub firm': 'budynki biurowe',
    'centrum informacyjne': 'budynki biurowe',
    'centrum telekomunikacyjne': 'budynki biurowe',
    'budynek kontroli ruchu kolejowego': 'budynki biurowe',
    'budynek kontroli ruchu powietrznego': 'budynki biurowe',

    # Healthcare (budynki szpitali i inne budynki opieki zdrowotnej)
    'szpital': 'budynki szpitali i inne budynki opieki zdrowotnej',
    'placówka ochrony zdrowia': 'budynki szpitali i inne budynki opieki zdrowotnej',
    'hospicjum': 'budynki szpitali i inne budynki opieki zdrowotnej',
    'sanatorium': 'budynki szpitali i inne budynki opieki zdrowotnej',
    'klinika weterynaryjna': 'budynki szpitali i inne budynki opieki zdrowotnej',
    'jednostka ratownictwa medycznego': 'budynki szpitali i inne budynki opieki zdrowotnej',
    'stacja krwiodawstwa': 'budynki szpitali i inne budynki opieki zdrowotnej',
    'żłobek': 'budynki szpitali i inne budynki opieki zdrowotnej',
    'dom opieki społecznej': 'budynki szpitali i inne budynki opieki zdrowotnej',
    'dom dla bezdomnych': 'budynki szpitali i inne budynki opieki zdrowotnej',
    'dom dziecka': 'budynki szpitali i inne budynki opieki zdrowotnej',
    'placówka opiekuńczo-wychowawcza': 'budynki szpitali i inne budynki opieki zdrowotnej',
    'ośrodek pomocy społecznej': 'budynki szpitali i inne budynki opieki zdrowotnej',
    'izba wytrzeźwień': 'budynki szpitali i inne budynki opieki zdrowotnej',
    'stacja sanitarno-epidemiologiczna': 'budynki szpitali i inne budynki opieki zdrowotnej',

    # Other (pozostałe budynki niemieszkalne)
    'archiwum': 'pozostałe budynki niemieszkalne',
    'stacja meteorologiczna': 'pozostałe budynki niemieszkalne',
    'stacja hydrologiczna': 'pozostałe budynki niemieszkalne',
    'stacja nadawcza radia i telewizji': 'pozostałe budynki niemieszkalne',
    'toaleta publiczna': 'pozostałe budynki niemieszkalne',
    'krematorium': 'pozostałe budynki niemieszkalne',
    'dom pogrzebowy': 'pozostałe budynki niemieszkalne',
    'budynki cmentarne': 'pozostałe budynki niemieszkalne',
    'garaż': 'pozostałe budynki niemieszkalne',
    'parking wielopoziomowy': 'pozostałe budynki niemieszkalne',

    'latarnia morska': 'pozostałe budynki niemieszkalne',
    'przejście graniczne': 'pozostałe budynki niemieszkalne',
    '': 'pozostałe budynki niemieszkalne'  # Empty string goes to "other"
}


def get_density_level(levels):
    """Determine density level based on number of floors."""
    try:
        levels = float(levels)
    except (TypeError, ValueError):
        return 'medium'

    if levels <= 2: return 'low'
    if levels <= 10: return 'medium'
    return 'high'


def adjust_color(base_color, density='medium'):
    """Adjust color based on density level."""
    rgb = mcolors.hex2color(base_color)
    factor = DENSITY_FACTORS.get(density, 1.0)
    return mcolors.rgb2hex([min(1, max(0, c * factor)) for c in rgb])


def get_outline_color(fill_color):
    """Generate outline color that's proportionally brighter than the fill color."""
    if fill_color == '#4D4D4D':  # Special case for "other" buildings
        return '#666666'

    rgb = mcolors.hex2color(fill_color)
    return mcolors.rgb2hex([min(1, c * 1.1) for c in rgb])


def get_building_category(fsbud):
    """
    Get the main building category from detailed FSBUD function.
    If building has multiple functions (separated by '|'),
    returns the highest priority category based on special rules:

    1. Train/bus stations ('dworzec') always take priority
    2. Residential buildings ('budynki mieszkalne') take priority in mixed-use
    3. Shopping centers ('centrum handlowe') take priority
    """
    if not isinstance(fsbud, str) or not fsbud.strip():
        return 'pozostałe budynki niemieszkalne'

    functions = [f.strip() for f in fsbud.split('|')]

    # Special case handling based on specific functions
    for func in functions:
        # Transportation buildings always take priority
        if func in ['dworzec kolejowy', 'dworzec autobusowy', 'dworzec lotniczy']:
            return 'budynki transportu'

        # Shopping centers always take priority
        if func in ['centrum handlowe']:
            return 'budynki handlowo-usługowe'

    # Check if residential is present - it takes priority in mixed-use buildings
    for func in functions:
        if func in ['budynek jednorodzinny', 'budynek wielorodzinny']:
            return 'budynki mieszkalne'

    # If no special case applies, use the standard priority system
    CATEGORY_PRIORITY = [
        'budynki zabytkowe i kulturalne',  # Landmarks and significant cultural buildings first
        'budynki sakralne',  # Religious buildings second
        'budynki przemysłowe i magazynowe',  # Industrial and storage buildings third
        'budynki mieszkalne',
        'budynki biurowe',
        'budynki oświaty i nauki',
        'budynki handlowo-usługowe',
        'budynki sportowe i rozrywkowe',
        'budynki transportu',
        'budynki urzędów i administracji publicznej',
        'budynki szpitali i inne budynki opieki zdrowotnej',
        'budynki produkcyjne, usługowe i gospodarcze dla rolnictwa',
        'pozostałe budynki niemieszkalne'
    ]

    categories = [FUNCTION_TO_CATEGORY.get(func, 'pozostałe budynki niemieszkalne')
                  for func in functions]

    # Count occurrences of each category
    category_counts = {}
    for cat in categories:
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # Sort by count (descending) and then by priority for ties
    sorted_categories = sorted(
        category_counts.items(),
        key=lambda x: (-x[1], CATEGORY_PRIORITY.index(x[0]))
    )

    return sorted_categories[0][0]
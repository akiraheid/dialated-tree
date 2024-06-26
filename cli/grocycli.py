#!/usr/bin/env python3

from argparse import ArgumentParser
from difflib import SequenceMatcher
import json
from os import environ
from pprint import pprint
import re
from sys import exit
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pygrocy import Grocy

api_key = environ.get('GROCY_API_KEY')
url = environ.get('GROCY_URL')
port = environ.get('GROCY_PORT', 80)
headers = {'GROCY-API-KEY': api_key,
        'accept': 'application/json',
        'Content-Type': 'application/json',
        }

grocy = None
unit_nicknames = {
        ' c ': 'cup',
        'clove': 'teaspoon',
        'cup': 'cup',
        'dash': 'gram',
        'dashes': 'gram',
        'floz': 'fluid ounce',
        'fluid ounce': 'fluid ounce',
        ' g ': 'gram',
        'gram': 'gram',
        'gal': 'gallon',
        'gallon': 'gallon',
        ' l ': 'liter',
        'liter': 'liter',
        'lb': 'pound',
        'ml': 'milliliter',
        'oz': 'ounce',
        'ounce': 'ounce',
        'pinch': 'ounce',
        'pound': 'pound',
        'qt': 'quart',
        'quart': 'quart',
        'tablespoon': 'tablespoon',
        'tbsp': 'tablespoon',
        'teaspoon': 'teaspoon',
        'tsp': 'teaspoon',
        }

# Commonly used ingredient names mapped to a (name, note)
product_nicknames = {
        'all purpose flour': ['flour', None],
        'all-purpose flour': ['flour', None],
        'allpurpose flour': ['flour', None],
        'ap flour': ['flour', None],
        'boiled or steamed spinach': ['spinach', 'boiled or steamed'],
        'butter': ['unsalted butter', None],
        'cinnamon': ['ground cinnamon', None],
        'garbanzo beans': ['chickpea', None],
        'garlic cloves': ['garlic', None],
        'granulated sugar': ['sugar', None],
        'kosher salt': ['salt', 'kosher'],
        'lukewarm water': ['water', 'lukewarm'],
        'melted butter': ['unsalted butter', 'melted'],
        'milk': ['whole milk', None],
        'russet potatoes': ['russet potato', None],
        'softened butter': ['unsalted butter', 'softened'],
        'warm water': ['water', 'warm'],
        'whole wheat flour': ['wheat flour', None],
        'unbleached all-purpose flour': ['flour', 'unbleached'],
        'yeast': ['active dry yeast', None],
        }

# Sometimes the ingredient specifies the preparation before the product
prep_verbs = [
        'chopped',
        'diced',
        'freshly ground',
        'freshly squeezed',
        'grated',
        'large',
        'ripe',
        'smooth',
        ]

money_pat = re.compile(r'\(\$\d+\.\d\d\)')
amount_pat = r'(?P<amount>\d+ to \d+|\d+\s?-\s?\d+|\d* ?\d+/\d+|\d+(?:\.\d+)?)'
unit_pat = f'(?P<unit>{"|".join(unit_nicknames)})?'
product_pat = r'(?P<product>[\w\s-]*\w+)'
note_pat = r'(?P<note>,\s+[\s\w]+|\([\w\s]+\))*'
full_pat = amount_pat + r'\s+' + unit_pat + r's?\s*' + product_pat + r'\s*' \
        + note_pat
ingredient_pat = re.compile(full_pat)
can_pat = re.compile(r'\d+\s+\(\s*' + amount_pat + r'\s+' + unit_pat \
        + r's?\s*\)\s+can\s+' + product_pat + r'\s*' + note_pat)
can_pat2 = re.compile(r'\d+\s+' + amount_pat + r'\s*' + unit_pat \
        + r'\s*\.\s+can\s+' + product_pat + r'\s*' + note_pat)
auto = False

#class IngredientParser():
#
#    def __init__(self):
#        amount_pat = r''
#        unit_pat = r''
#        product_pat = r'(?P<product>[\w\s-]*\w+)'
#        note_pat = r'(?P<note>,\s+[\s\w]+|\([\w\s]+\))*'
#        full_pat = amount_pat + r'\s+' + unit_pat + r's?\s*' + product_pat\
#                + r'\s*' + note_pat
#
#        self.ingredient_pat = re.compile(pat)
#
#    def translate(self, ingredient):
#        """Translate ingredient from a known, unparsable ingredient to a
#        useful ingredient."""
#        if 'cooking spray' == ingredient.lower():
#            return '1 tbsp olive oil'
#
#        return ingredient
#
#    def parse_amount(self, string):
#        """Parse a number from a string."""
#        if ' to ' in string:
#            amount = amount.split(' to ')[0].strip()
#        elif '-' in amount:
#            amount = amount.split('-')[0].strip()
#
#        # Handle integers, decimals, and fractions
#        print(f'parse_amount(): {part}')
#        try:
#            return int(part)
#        except ValueError:
#            try:
#                return float(part)
#            except ValueError:
#                try:
#                    # Might be a fraction
#                    parts = part.split(' ')
#
#                    if '/' in parts[0]:
#                        whole = 0
#                        fraction_parts = parts[0].split('/')
#                    else:
#                        whole = float(parts[0])
#                        fraction_parts = parts[1].split('/')
#
#                    print(f'whole: {whole}')
#                    print(f'fraction_parts: {fraction_parts}')
#                    decimal = int(fraction_parts[0]) / int(fraction_parts[1])
#                    return whole + decimal
#                except Exception as e:
#                    return None
#
#    def parse(self, ingredient):
#        ingredient = translate(ingredient)
#
#        amatch = self.ingredient_pat.match(ingredient)
#        if not amatch:
#            return (None, None, None, None)

class GrocyApi():

    productiddict = None
    products = None
    units = None

    def __init__(self, url, api_key, port=80):
        self.url = url
        self.port = port
        self.api_key = api_key
        self.headers = {'GROCY-API-KEY': api_key}
        self.grocy = Grocy(url, api_key, port=port)

        self.products = self.all_products()
        self.productiddict = {x.name: x.id for x in self.products}
        self.units = {x.get('name'): x.get('id') for x in self.get_quantity_units()}

    def all_products(self):
        return self.grocy.all_products()

    def delete(self, url):
        req = Request(url=url, headers=headers, method='DELETE')
        with urlopen(req) as f:
            ret = f.read().decode('utf-8')
            return json.loads(ret if ret else '{}')

    def get(self, url):
        req = Request(url=url, method='GET')
        with urlopen(req) as f:
            return json.loads(f.read().decode('utf-8'))

    def get_quantity_units(self):
        return get(f'{self.url}:{self.port}/api/objects/quantity_units')

    def post(self, url, data):
        data = json.dumps(data).encode('utf-8')
        req = Request(url=url, headers=headers, data=data, method='POST')
        try:
            with urlopen(req) as f:
                return json.loads(f.read().decode('utf-8'))
        except HTTPError as e:
            print(e.code)
            print(e.read())
            raise e

    def post_recipe(self, name, description, servings):
        data = {
                'name': name,
                'description': description,
                'base_servings': servings,
                'desired_servings': servings,
                }

        res = self.post(f'{self.url}:{self.port}/api/objects/recipes', data=data)
        return res.get('created_object_id')

    def post_product(self, name, unitid):
        data = {
                'name': name,
                'location_id': 1,
                'qu_id_consume': unitid,
                'qu_id_price': unitid,
                'qu_id_purchase': unitid,
                'qu_id_stock': unitid,
                }
        res = self.post(f'{self.url}:{self.port}/api/objects/products', data=data)
        self.products = self.all_products()
        return res.get('created_object_id')

    def add_ingredient_to_recipe(self, recipeid, productid, unitid, amount, group_name=None, note=None, price_factor=1):
        data = {
                'recipe_id': recipeid,
                'product_id': productid,
                'qu_id': unitid,
                'amount': amount,
                'price_factor': price_factor,
                'variable_amount': amount,
                'ingredient_group': group_name,
                'note': note,
                }

        res = self.post(f'{self.url}:{self.port}/api/objects/recipes_pos', data=data)
        return res.get('created_object_id')

    def delete_recipe(self, recipeid):
        return self.delete(f'{self.url}:{self.port}/api/objects/recipes/{recipeid}')

def get(url):
    req = Request(url=url, headers=headers, method='GET')
    with urlopen(req) as f:
        return json.loads(f.read().decode('utf-8'))

def process_recipe(data):
    """Grocy treats recipes and ingredients as separate, linking products to the
    recipe via the recipe_pos.

    A recipe is the name, description (directions), and servings."""
    title = data.get('title')
    author = data.get('author')
    host = data.get('host')
    name = f'*AUTO-IMPORT* {title} ({host} - {author})'

    # Directions are HTML in Grocy
    description = ('').join([f'<p>{x}</p>' for x in data.get('instructions_list')])

    nutrients = data.get('nutrients')
    description += '<p>Nutrition Facts</p><table>'
    for key in nutrients:
        description += f'<tr><td>{key}</td><td>{nutrients[key]}</td></tr>'

    description += '</table>'

    source = data.get('canonical_url')
    description += f'<p>Source: {source}</p>'

    category = data.get('category')
    description += f'<p>Category: {category}</p>'

    total_minutes = data.get('total_time')
    description += f'<p>Total minutes: {total_minutes} minutes</p>'

    servings = data.get('yields')
    servings = servings.lower().replace('servings', '')
    servings = servings.replace('serving', '').strip()

    try:
        servings = int(servings)
    except ValueError:
        print(f'Couldn\'t convert "{servings}" to integer.')
        if auto:
            exit(1)

        while True:
            try:
                servings = int(input(f'Servings: ').strip())
                break
            except ValueError:
                pass

    return (name, description, servings)

def get_similar_products(text, ratio=0.5):
    ret = []
    for x in grocy.products:
        similarity = SequenceMatcher(
                lambda y: y == ' ',
                text.lower(),
                x.name.lower()).ratio()

        if similarity > ratio:
            ret.append([x.name, x.id, similarity])

    sorted(ret, key=lambda x: x[2])
    return ret

def interactive_get_uint(msg='Enter a positive integer: '):
    ret = None
    while True:
        try:
            ret = int(input(msg).strip())
            if ret >= 0:
                break
        except ValueError:
            print('Could not convert to integer')

    return ret

def interative_get_ufloat(msg='Enter positive decimal: '):
    ret = None
    while True:
        try:
            ret = float(input(msg).strip())
            if ret >= 0:
                break
        except ValueError:
            print('Could not convert to decimal')

    return ret

def interactive_get_choice(choices, msg='Select an option: '):
    while True:
        for idx in range(len(choices)):
            print(f'{idx+1}) {choices[idx][0]}')

        choice = interactive_get_uint(msg) - 1

        if choice >= 0 and choice < len(choices):
            return choices[choice][1]

def interactive_make_product(name=None):
    """Make a Product in Grocy after getting the required fields from the
    user."""
    print('Creating product')
    if not name:
        name = input('Enter product name: ').strip()

    print('Select a default unit for this product')
    units = grocy.units
    choices = [[x.get('name'), x.get('id')] for x in units]
    unitid = interactive_get_choice(choices, msg='Select a unit: ')

    return grocy.post_product(name, unitid)

def parse_unit(ingredient):
    print(f'parse_unit {ingredient}')
    guesses = [unit_nicknames[k] for k in unit_nicknames if k in ingredient.lower()]
    unit_guess = guesses[0] if guesses else None

    if unit_guess:
        for unit in grocy.units:
            if unit_guess == unit.get('name'):
                print(f'Automatically parsed unit "{unit_guess}"')
                return (unit.get('id'), unit.get('name'))

    return (None, None)

def parse_amount(part):
    # Handle integers, decimals, and fractions
    print(f'parse_amount(): {part}')
    try:
        return int(part)
    except ValueError:
        try:
            return float(part)
        except ValueError:
            try:
                # Might be a fraction
                parts = part.split(' ')

                if '/' in parts[0]:
                    whole = 0
                    fraction_parts = parts[0].split('/')
                else:
                    whole = float(parts[0])
                    fraction_parts = parts[1].split('/')

                print(f'whole: {whole}')
                print(f'fraction_parts: {fraction_parts}')
                decimal = int(fraction_parts[0]) / int(fraction_parts[1])
                return whole + decimal
            except Exception as e:
                return None

def sanitize_ingredient(ingredient):
    # Remove possible ($0.00)
    amatch = money_pat.search(ingredient)
    if amatch:
        ingredient = ingredient.replace(amatch[0], '').strip()
        print(f'Removed {amatch[0]}')

    # Remove any extra characters
    ingredient = re.sub(r'[^\w\s\./]', '', ingredient)

    return ingredient

def parse_product(text):
    print(f'Parsing product from "{text}"')
    matches = [x.id for x in grocy.products if x.name.lower() == text.lower()]
    if matches:
        return matches[0] if matches else None

    return product_nicknames.get(text)

def guess_ingredient(ingredient):
    amount = None
    note = None
    productid = None
    unitid = None

    (unitid, unit_text) = parse_unit(ingredient)

    if not unitid:
        return (None, None, None, None)

    parts = ingredient.split(' ')
    for idx in range(len(parts)):
        if unit_text in parts[idx]:
            part = ' '.join(parts[:idx]).strip()
            amount = parse_amount(part)

    if not amount:
        return (None, None, None, None)

    for idx in range(len(parts)):
        if unit_text in parts[idx]:
            part = ' '.join(parts[idx+1:]).strip()
            productid = parse_product(part)
            break

    return (productid, unitid, amount, note)

def parse_ingredient(ingredient):
    print(f'Parsing {ingredient}')
    if ingredient.lower().startswith('handful'):
        ingredient = '1/2 cup ' + ingredient[7:].strip()

    if ingredient.lower() == 'cooking spray':
        ingredient = '1 tbsp olive oil'

    amatch = can_pat2.match(ingredient)

    if not amatch:
        amatch = can_pat.match(ingredient)

    if not amatch:
        amatch = ingredient_pat.match(ingredient)

    if not amatch:
        return (None, None, None, None)

    print(amatch.groups())

    amount = amatch.group('amount')
    unit = amatch.group('unit') or 'count'
    product = amatch.group('product')
    note = amatch.group('note')

    if ' to ' in amount:
        amount = amount.split(' to ')[0].strip()
    elif '-' in amount:
        amount = amount.split('-')[0].strip()

    amount = parse_amount(amount)

    unitid = grocy.units.get(unit)
    if not unitid:
        unit = unit_nicknames.get(unit) if unit else unit
        unitid = grocy.units.get(unit)

    notes = []
    if note and note.startswith(', '):
        notes = note[2:]

    notes = [notes] if notes else []

    # Sanitize product in case ingredient specifies prep in product name
    parts = product.split(' ')
    for idx in range(len(parts)):
        verb_guess = ' '.join(parts[:idx])
        if verb_guess in prep_verbs:
            notes.append(verb_guess)
            product = ' '.join(parts[idx:])
            print('Found prep info in product name.')
            print(f'product: {product}')
            print(f'notes: {notes}')
            break

    if product.lower().startswith('fresh'):
        product = product[5:].strip()

    productid = grocy.productiddict.get(product)
    if not productid:
        info = product_nicknames.get(product)
        product = info[0] if info else product
        productid = grocy.productiddict.get(product)
        if info and info[1]:
            notes.append(info[1])

    if not productid:
        similars = get_similar_products(product, ratio=0.7)
        if similars:
            info = similars[0]
            productid = info[1]
            print(f'Similarity of best match "{info[0]}": {info[2]}')

    if product == 'garlic' and unit == 'count':
        unit = 'teaspoon'
        unitid = grocy.units.get(unit)

    note = ', '.join(notes) if notes else None

    print(f'productid: {productid} ({product})')
    print(f'amount: {amount}')
    print(f'unitid: {unitid} ({unit})')
    print(f'note: {note}')

    return (productid, unitid, amount, note)

def process_ingredient(ingredient):
    print(f'Processing: "{ingredient}"')

    ingredient = sanitize_ingredient(ingredient)

    if auto:
        (productid, unitid, amount, note) = parse_ingredient(ingredient)
    else:
        (productid, unitid, amount, note) = guess_ingredient(ingredient)

    if not productid:
        print(f'\nCould not parse product from "{ingredient}"')
        if auto:
            exit(1)

        print(f'What is the name of the ingredient in "{ingredient}"?')
        name = input(f'Name: ').strip()

        similar = get_similar_products(name)
        if similar:
            similar += [['Make new product', None]]
            print('Closest matching products in Grocy are:')
            productid = interactive_get_choice(similar)

        if not productid:
            productid = interactive_make_product(name)

    if not unitid:
        print(f'\nCould not parse unit from "{ingredient}"')
        if auto:
            exit(1)

        print(f'What is the unit in "{ingredient}"?')
        units = [[x.get('name'), x.get('id')] for x in grocy.units]
        while not unitid:
            unitid = interactive_get_choice(units)

    if not amount:
        print(f'\nCould not parse amount from "{ingredient}"')
        if auto:
            exit(1)

        print(f'What is the amount of the ingredient "{ingredient}"?')
        amount = interative_get_ufloat(msg='Enter amount: ')

    return (productid, unitid, amount, note)

def add_recipe(args):
    file = args.file

    print(f'Adding recipe from file "{file}"')

    data = None
    with open(file, 'r') as fp:
        data = json.load(fp)

    (recipe_name, description, servings) = process_recipe(data)

    groups = data.get('ingredient_groups')
    if not groups:
        print('No ingredients found. Nothing to upload.')
        exit(1)

    ingredient_groups = {}
    for group in data.get('ingredient_groups'):
        group_name = group.get('purpose')

        ingredients = group.get('ingredients')
        info = []
        for ingredient in ingredients:
            info.append(process_ingredient(ingredient))

        ingredient_groups[group_name] = info

    print(f'Uploading recipe "{recipe_name}"')
    recipeid = grocy.post_recipe(recipe_name, description=description, servings=servings)
    for group in ingredient_groups:
        for (productid, unitid, amount, note) in ingredient_groups[group]:
            print(f'Uploading ingredient "{productid}"')
            try:
                grocy.add_ingredient_to_recipe(recipeid, productid, unitid, amount, group_name, note=note)
            except Exception:
                print('Error: Failed to add ingredient. Deleting incomplete recipe.')
                grocy.delete_recipe(recipeid)
                exit(1)

    print('Uploaded successfully.')


def parseargs():
    parser = ArgumentParser(description='A CLI interface for Grocy.')
    subparsers = parser.add_subparsers(required=True)

    padd = subparsers.add_parser('add', help='Add an entity.')

    paddsp = padd.add_subparsers(required=True)
    paddrecipe = paddsp.add_parser('recipe', help='Add a recipe.')
    paddrecipe.add_argument('file', type=str, help='File with entity to add.')
    autohelp = 'Try to import a recipe without user assistance. Exits on first issue.'
    paddrecipe.add_argument('--auto', action='store_true', default=False, help=autohelp)
    paddrecipe.set_defaults(func=add_recipe)

    return parser.parse_args()

if __name__ == '__main__':
    args = parseargs()

    if not api_key:
        print('Grocy API key not defined.')
        exit(1)

    if not url:
        print('Grocy URL not provided.')
        exit(1)

    grocy = GrocyApi(url, api_key, port=port)
    auto = args.auto

    args.func(args)

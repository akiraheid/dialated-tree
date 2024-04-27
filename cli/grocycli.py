#!/usr/bin/env python3

from argparse import ArgumentParser
from difflib import SequenceMatcher
import json
from os import environ
from pprint import pprint
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
units = {}

class GrocyApi():

    # USED FOR TESTING
    _productid = 0
    _rposid = 0
    _recipeid = 0
    # END USED FOR TESTING

    products = None
    units = None

    def __init__(self, url, api_key, port=80):
        self.url = url
        self.port = port
        self.api_key = api_key
        self.headers = {'GROCY-API-KEY': api_key}
        self.grocy = Grocy(url, api_key, port=port)

        self.products = self.all_products()
        self.units = self.get_quantity_units()

    def all_products(self):
        return self.grocy.all_products()

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
            exit(1)

    def post_recipe(self, name, description, servings):
        data = {
                'name': name,
                'description': description,
                'base_servings': servings,
                'desired_servings': servings,
                }

        #print("post_recipe()")
        pprint(data)
        #self._recipeid += 1
        #return self._recipeid
        res = self.post(f'{self.url}:{self.port}/api/objects/recipes', data=data)
        return res.get('created_object_id')

    def post_product(self, name, unitid):
        #self._productid += 1
        #self.products = grocy.all_products()
        #return self._productid
        data = {
                'name': name,
                'location_id': 1,
                'qu_id_consume': unitid,
                'qu_id_price': unitid,
                'qu_id_purchase': unitid,
                'qu_id_stock': unitid,
                }
        res = self.post(f'{self.url}:{self.port}/api/objects/products', data=data)
        return res.get('created_object_id')

    def add_ingredient_to_recipe(self, recipeid, productid, unitid, amount, price_factor=1):
        data = {
                'recipe_id': recipeid,
                'product_id': productid,
                'qu_id': unitid,
                'amount': amount,
                'price_factor': price_factor,
                'variable_amount': amount,
                }

        #self._rposid += 1
        #print('add_ingredient_to_recipe()')
        #pprint(data)
        #return self._rposid
        res = self.post(f'{self.url}:{self.port}/api/objects/recipes_pos', data=data)
        return res.get('created_object_id')

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
    name = f'{title} ({host} - {author})'
    name = input(f'Name ({name}): ').strip() or name

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
        while True:
            print(f'Couldn\'t convert "{servings}" to integer.')
            try:
                servings = int(input(f'Servings: ').strip())
                break
            except ValueError:
                pass

    return grocy.post_recipe(name, description=description, servings=servings)

def get_similar_products(text):
    return [[x.name, x.id] for x in grocy.products if
        SequenceMatcher(lambda y: y == ' ',
            text.lower(),
            x.name.lower()
        ).ratio() > 0.5
    ]

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

def process_ingredient(ingredient):
    print(f'Processing: "{ingredient}"')

    # Find product with matching name
    productid = None
    unitid = None
    parts = ingredient.split(' ')
    amount_guess = parts[0]
    unit_guess = parts[1]
    name_guess = ' '.join(parts[2:])

    for product in grocy.products:
        if name_guess == product.name:
            productid = product.id
            break

    if not productid:
        print('No existing ingredient name matches exactly')
        print(f'What is the name of the ingredient in "{ingredient}"?')
        name = input(f'Name ({name_guess}): ').strip() or name_guess

        similar = get_similar_products(name)
        if similar:
            similar += [['Make new product', None]]
            print('Closest matching names are:')
            productid = interactive_get_choice(similar)

        if not productid:
            productid = interactive_make_product(name)

    print(f'Product ID: {productid}')

    unitid = None
    for unit in grocy.units:
        if unit_guess == unit.get('name'):
            print(f'Automatically parsed unit "{unit_guess}"')
            unitid = unit.get('id')
            break

    if not unitid:
        print(f'What is the unit in "{ingredient}"?')
        units = [[x.get('name'), x.get('id')] for x in grocy.units]
        while not unitid:
            unitid = interactive_get_choice(units)

    print(f'What is the amount of the ingredient "{ingredient}"?')
    amount = interative_get_ufloat(msg='Enter amount: ')

    return (productid, unitid, amount)

def add_recipe(args):
    file = args.file

    data = None
    with open(file, 'r') as fp:
        data = json.load(fp)

    name = data.get('title')

    recipeid = process_recipe(data)

    ingredients = []
    for ingredient in data.get('ingredients'):
        (productid, unitid, amount) = process_ingredient(ingredient)
        grocy.add_ingredient_to_recipe(recipeid, productid, unitid, amount)

def parseargs():
    parser = ArgumentParser(description='A CLI interface for Grocy.')
    subparsers = parser.add_subparsers(required=True)

    padd = subparsers.add_parser('add', help='Add an entity.')

    paddsp = padd.add_subparsers(required=True)
    paddrecipe = paddsp.add_parser('recipe', help='Add a recipe.')
    paddrecipe.add_argument('file', type=str, help='File with entity to add.')
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

    args.func(args)

import requests
import pandas as pd
import time
import re
import unicodedata
from fuzzywuzzy import process
from dotenv import load_dotenv
import os
import json

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# Obter chaves de API das variáveis de ambiente
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
CUSTOM_SEARCH_ENGINE_ID = os.getenv('CUSTOM_SEARCH_ENGINE_ID')

# URLs das APIs
GOOGLE_PLACES_SEARCH_URL = 'https://maps.googleapis.com/maps/api/place/textsearch/json'
GOOGLE_PLACES_DETAILS_URL = 'https://maps.googleapis.com/maps/api/place/details/json'
GOOGLE_CUSTOM_SEARCH_URL = 'https://www.googleapis.com/customsearch/v1'

def normalize_name(name):
    """
    Normaliza o nome da empresa:
    - Remove acentos
    - Remove caracteres especiais
    - Remove sufixos comerciais como Ltda., S/A, etc.
    - Padroniza espaços
    """
    if not name:
        return ""
    # Remover acentos
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    # Remover sufixos comerciais
    name = re.sub(r'\b(Ltda\.|Ltda|EIRELI|S\/A|SA|Limited|Ltd)\b', '', name, flags=re.IGNORECASE)
    # Remover caracteres especiais
    name = re.sub(r'[^\w\s]', '', name)
    # Padronizar espaços
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def get_companies_in_santos(query, next_page_token=None):
    """
    Busca empresas em Santos, SP usando a Google Places API.
    """
    params = {
        'query': query,
        'location': '-23.9608,-46.3336',  # Coordenadas aproximadas de Santos, SP
        'radius': 10000,  # 10 km
        'key': GOOGLE_API_KEY,
        'type': 'restaurant'  # Filtra por restaurantes
    }
    if next_page_token:
        params['pagetoken'] = next_page_token

    response = requests.get(GOOGLE_PLACES_SEARCH_URL, params=params)
    if response.status_code != 200:
        print(f"Erro na requisição de empresas: {response.status_code}")
        return {}
    data = response.json()
    print(f"Requisição de empresas retornou {len(data.get('results', []))} resultados.")
    return data

def get_company_details(place_id):
    """
    Obtém detalhes de uma empresa usando o Place ID da Google Places API.
    """
    params = {
        'place_id': place_id,
        'fields': 'name,formatted_address,rating,formatted_phone_number,types,geometry/location,user_ratings_total',
        'key': GOOGLE_API_KEY
    }
    response = requests.get(GOOGLE_PLACES_DETAILS_URL, params=params)
    if response.status_code != 200:
        print(f"Erro na requisição de detalhes para place_id {place_id}: {response.status_code}")
        return {}
    result = response.json()
    if 'result' not in result:
        print(f"Detalhes não encontrados para place_id: {place_id}")
        return {}
    print(f"Detalhes coletados para {result['result'].get('name', 'N/A')}")
    return result

def get_social_media_links(company_name, city='Santos SP'):
    """
    Busca links de Instagram e Facebook usando a Google Custom Search API.
    """
    if not CUSTOM_SEARCH_ENGINE_ID:
        print("Custom Search Engine ID não está configurado.")
        return []
    
    company_name_clean = normalize_name(company_name)
    query = f'"{company_name_clean}" {city} site:facebook.com OR site:instagram.com'
    params = {
        'key': GOOGLE_API_KEY,  
        'cx': CUSTOM_SEARCH_ENGINE_ID,
        'q': query,
        'num': 5  # Limita a 5 resultados
    }
    response = requests.get(GOOGLE_CUSTOM_SEARCH_URL, params=params)
    if response.status_code != 200:
        print(f"Erro na requisição de redes sociais para {company_name}: {response.status_code}")
        return []
    try:
        results = response.json()
    except ValueError:
        print(f"Resposta não está no formato JSON para {company_name}.")
        return []
    if 'items' not in results:
        print(f"Nenhum item encontrado na pesquisa de redes sociais para {company_name}.")
        return []
    links = []
    for item in results.get('items', []):
        links.append(item['link'])
    print(f"Links de redes sociais encontrados para {company_name}: {links}")
    return links

def collect_data():
    """
    Coleta dados de restaurantes em Santos, SP, e seus links de redes sociais.
    """
    all_companies = []
    query = 'restaurantes em Santos SP'
    data = get_companies_in_santos(query)
    if not data:
        print("Nenhum dado retornado para a consulta de empresas.")
        return pd.DataFrame()
    results = data.get('results', [])
    print(f"Primeiro lote de resultados: {len(results)} restaurantes.")
    next_page_token = data.get('next_page_token')
    
    while True:
        for result in results:
            place_id = result.get('place_id')
            if not place_id:
                print("Place ID não encontrado para um resultado.")
                continue
            details = get_company_details(place_id)
            company_info = details.get('result', {})
            if not company_info:
                print(f"Nenhum detalhe encontrado para place_id: {place_id}")
                continue
            company_name = company_info.get('name', 'N/A')
            print(f"Processando empresa: {company_name}")
            
            # Coletar links de redes sociais
            social_links = get_social_media_links(company_name)
            
            # Extrair segmentos de endereço
            formatted_address = company_info.get('formatted_address', '')
            address_components = parse_address(formatted_address)
            
            # Adicionar dados ao conjunto
            company_data = {
                'Name': company_name,
                'Address': formatted_address,
                'Neighborhood': address_components.get('neighborhood', 'N/A'),
                'Street': address_components.get('route', 'N/A'),
                'City': address_components.get('locality', 'N/A'),
                'Rating': company_info.get('rating', 0),
                'UserRatingsTotal': company_info.get('user_ratings_total', 0),  
                'Phone': company_info.get('formatted_phone_number', 'N/A'),
                'Types': company_info.get('types', []),
                'Location': company_info.get('geometry', {}).get('location', {}),
                'SocialLinks': social_links
            }
            all_companies.append(company_data)
        if next_page_token:
            print("Obtendo a próxima página de resultados...")
            time.sleep(2)  # Aguarda para o next_page_token estar ativo
            data = get_companies_in_santos(query, next_page_token)
            if not data:
                print("Nenhum dado retornado para a próxima página.")
                break
            results = data.get('results', [])
            print(f"Próximo lote de resultados: {len(results)} restaurantes.")
            next_page_token = data.get('next_page_token')
        else:
            break
    if not all_companies:
        print("Nenhuma empresa coletada.")
        return pd.DataFrame()
    df = pd.DataFrame(all_companies)
    print("Dados coletados com sucesso:")
    print(df.head())
    return df

def parse_address(formatted_address):
    """
    Analisa o endereço formatado e extrai componentes como bairro e rua.
    """
    # Utilize a Google Places API ou Regex para extrair componentes específicos
    # Aqui, simplificamos usando Regex
    address_components = {}
    # Exemplo de endereço: "Rua Doutor Mário Moura, 123 - Boqueirão, Santos - SP, 11060-000"
    match = re.match(r'^(.*?),\s*(\d+).*?-\s*(.*?),\s*(Santos - SP).*$', formatted_address)
    if match:
        address_components['route'] = match.group(1)
        address_components['street_number'] = match.group(2)
        address_components['neighborhood'] = match.group(3)
        address_components['locality'] = 'Santos'
    return address_components

def classify_company_size(user_ratings_total):
    """
    Classifica o porte da empresa com base no número de avaliações.
    """
    if user_ratings_total is None or user_ratings_total == 0:
        return 'Pequena'
    elif user_ratings_total >= 100:
        return 'Grande'
    elif user_ratings_total >= 20:
        return 'Média'
    else:
        return 'Pequena'

def main():
    # Coletar dados
    print("Coletando dados dos restaurantes...")
    df = collect_data()
    print(f"Total de restaurantes coletados: {len(df)}")
    
    if df.empty:
        print("O DataFrame está vazio. Verifique as requisições da API.")
        return
    
    # Classificar o porte das empresas
    df['CompanySize'] = df['UserRatingsTotal'].apply(classify_company_size)
    
    # Selecionar colunas relevantes
    df = df[[
        'Name',
        'Address',
        'Neighborhood',
        'Street',
        'City',
        'Rating',
        'UserRatingsTotal',
        'Phone',
        'Types',
        'Location',
        'SocialLinks',
        'CompanySize'
    ]]
    
    # Converter o DataFrame para JSON
    output_json = df.to_json(orient='records', force_ascii=False, indent=4)
    
    # Salvar o JSON em um arquivo
    with open('restaurantes_santos_sp.json', 'w', encoding='utf-8') as f:
        f.write(output_json)
    
    print("Dados salvos no arquivo 'restaurantes_santos_sp.json'.")

if __name__ == '__main__':
    main()

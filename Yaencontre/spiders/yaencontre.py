import datetime
import json
import re

import scrapy
from scrapy import Request


class YaencontreSpider(scrapy.Spider):
    name = 'yaencontre'
    start_urls = ['https://www.yaencontre.com']
    zyte_key = '07a4b6f903574c1d8b088b55ff0265fc'  # Todo : YOUR API KEY FROM ZYTE
    custom_settings = {
        'FEED_URI': 'yaencontre.csv',
        'FEED_FORMAT': 'csv',
        'ZYTE_SMARTPROXY_ENABLED': True,
        'ZYTE_SMARTPROXY_APIKEY': zyte_key,
        'DOWNLOADER_MIDDLEWARES': {
            'scrapy_zyte_smartproxy.ZyteSmartProxyMiddleware': 610
        },
    }

    headers = {
        'authority': 'www.yaencontre.com',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,'
                  'image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'accept-language': 'en-US,en;q=0.9,de;q=0.8',
        'cache-control': 'max-age=0',
        'sec-ch-ua': '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Linux"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/107.0.0.0 Safari/537.36',
        'X-Crawlera-Region': 'fr',
        'X-Crawlera-Profile': 'pass'
    }
    listing_url = "https://api.yaencontre.com/v3/search?family={}&lang=es&location={}&" \
                  "operation={}&pageNumber={}&pageSize=26"
    image_pre = "https://media.yaencontre.com/img/photo/w1024/"

    def parse(self, response, **kwargs):
        all_categories = response.css('.panel  .nearCity a::attr(href)').getall()
        for category in all_categories:
            yield Request(url=response.urljoin(category),
                          callback=self.parse_listing,
                          meta={'dont_merge_cookies': True,
                                "dont_proxy": True}
                          )

    def parse_listing(self, response):
        json_data = re.findall('\\\\"query\\\\":{(.+?)},', response.text)[0].replace('\\', '')
        elements = json.loads("{}{}{}".format('{', json_data, '}'))
        url = self.listing_url.format(
            elements.get('family'),
            elements.get('location'),
            elements.get('operation'), 1)
        yield Request(
            url=url,
            callback=self.parse_listing_api,
            headers=self.headers,
            dont_filter=True,
            meta={'page': 1,
                  'family': elements.get('family'),
                  'location': elements.get('location'),
                  'operation': elements.get('operation'),
                  'dont_merge_cookies': True,
                  }
        )

    def parse_listing_api(self, response):
        json_data = json.loads(response.text)
        total_pages = json_data.get('result', {}).get('numPages', '')
        yield Request(
            url=response.url,
            callback=self.parse_api,
            headers=self.headers,
            meta={
                'family': response.meta['family'],
                'location': response.meta['location'],
                'operation': response.meta['operation'],
                'dont_merge_cookies': True,
                'total_pages': total_pages,
                'page': 1,
            }
        )

    def parse_api(self, response):
        json_data = json.loads(response.text)
        items = json_data.get('result', {}).get('items', '')
        for item in items:
            real_state = item.get('realEstate', {})
            url = f"{self.start_urls[0]}{real_state.get('url', '')}"
            images_load = real_state
            images = ['{}{}'.format(self.image_pre, image.get('slug', ''))
                      for image in images_load.get('images', {})]
            title = real_state.get('title', '')
            room_count = real_state.get('rooms', '')
            operation = real_state.get('operation', '')
            area = real_state.get('area', '')
            house_type = real_state.get('family', '')
            bathrooms = real_state.get('bathrooms', '')
            price = real_state.get('price', '')
            description = real_state.get('description', '')
            address = real_state.get('address', {}).get('qualifiedName', '')
            latitude = real_state.get('address', {}).get('geoLocation', {}).get('lat', '')
            longitude = real_state.get('address', {}).get('geoLocation', {}).get('lon', '')
            new_constructed = real_state.get('isNewConstruction', '')
            owner_type = real_state.get('owner', {}).get('type', {})
            owner_phone = real_state.get('owner', {}).get('virtualPhoneNumber', '')
            owner_name = real_state.get('owner', {}).get('name', {})
            data = {
                'Name': title.strip() if title else '',
                'Address': address,
                'Rooms': room_count,
                'Bathrooms': bathrooms,
                'Operation': operation,
                'Area': area,
                'price': price,
                'Latitude': latitude,
                'Longitude': longitude,
                'Type': house_type,
                'New Constructed': new_constructed,
                'image_urls': images,
                'Owner Type': owner_type,
                'Owner Phone': owner_phone,
                'Owner Name': owner_name,
            }
            yield Request(
                url=url,
                callback=self.detail_page,
                meta={'data': data,
                      'description': description}
            )
        current_page = response.meta['page']
        next__page = response.meta['page'] + 1
        if current_page < response.meta['total_pages']:
            url = self.listing_url.format(
                response.meta['family'],
                response.meta['location'],
                response.meta['operation'],
                next__page
            )
            yield Request(
                url=url,
                callback=self.parse_api,
                headers=self.headers,
                meta={
                    'family': response.meta['family'],
                    'location': response.meta['location'],
                    'operation': response.meta['operation'],
                    'page': next__page,
                    'dont_merge_cookies': True,
                    'total_pages': response.meta['total_pages']
                }
            )

    def detail_page(self, response):
        api_description = ' '.join(response.meta['description'].split()) if response.meta['description'] else ''
        certificates = response.xpath('//*[contains(@class,"energy-certificate")]//p/@data-rating').getall()
        description = ''.join(response.css('#details-description .box-readmore *::text').getall())
        data = response.meta['data']
        data['characteristics'] = ''.join(response.css('.characteristics li::text').getall())
        data['energy_certificates'] = ','.join(certificates)
        data['Description'] = ' '.join(description.split()) if description else api_description
        data['equipment'] = ','.join(response.css('#sticky-bar-limit-desktop li *::text').getall())
        data['Data Source'] = 'yaencontre'
        data['Date'] = datetime.datetime.now()
        data['Url'] = response.url
        yield data

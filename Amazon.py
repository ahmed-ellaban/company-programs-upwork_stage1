import random
from urllib.parse import urljoin

import requests
import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from helper import *
from minimum_sales_required import minimum_total_sales_of_search_group_for_results
from sales_rank_to_sales import run_class


def get_proxies():
    proxy_path = config_data.get('PROXIES_FILE_PATH')
    file = open(proxy_path, mode='r')
    proxies = []
    for url in file.readlines():
        proxies.append(
            f'http://{url.strip()}'
        )
    # proxies = [
    #     "http://ufenldeh:lim9gprvbsew@38.154.227.167:5868",
    #     "http://ufenldeh:lim9gprvbsew@185.199.229.156:7492",
    #     "http://ufenldeh:lim9gprvbsew@185.199.228.220:7300",
    #     "http://ufenldeh:lim9gprvbsew@185.199.231.45:8382",
    #     "http://ufenldeh:lim9gprvbsew@188.74.210.207:6286",
    #     "http://ufenldeh:lim9gprvbsew@188.74.183.10:8279",
    #     "http://ufenldeh:lim9gprvbsew@188.74.210.21:6100",
    #     "http://ufenldeh:lim9gprvbsew@45.155.68.129:8133",
    #     "http://ufenldeh:lim9gprvbsew@154.95.36.199:6893",
    #     "http://ufenldeh:lim9gprvbsew@45.94.47.66:8110"
    # ]
    return proxies


class AmazonSpider(scrapy.Spider):
    name = "amazon_Scope"

    skipped_list = set()
    custom_settings = {
        'LOG_LEVEL': 'INFO'
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logs = {}

    def start_requests(self):
        with open(config_data.get('INPUT_FILE_PATH'), mode='r') as f:
            for term in f.readlines():
                term = term.lower().strip()
                self.skipped_list.add(term)
                #     prompt = RULES.get('RULE_5_6_9').format(term).strip()
                #     data = get_gpt_payload(prompt)
                #
                #     yield scrapy.Request(
                #         url=API_URL_GPT,
                #         method='POST',
                #         headers=GPT_HEADERS,
                #         body=json.dumps(data),
                #         meta={'search_term': term}
                #     )
                api_url = f"https://completion.amazon.com/api/2017/suggestions?limit=11&prefix={term}&suggestion-type=WIDGET&suggestion-type=KEYWORD&page-type=Search&alias=aps&site-variant=desktop&version=3&event=onkeypress&wc=&lop=en_US&last-prefix=ceramic%20fire%20balls&avg-ks-time=7481&fb=1&mid=ATVPDKIKX0DER&plain-mid=1&client-info=search-ui"
                self.logs[term] = {}
                yield scrapy.Request(api_url, meta={'term': term},
                                     callback=self.parse_rule_1)

    def parse(self, response, **kwargs):
        """
            Implemented the 5,6 9 ruler here
            :param response:
            :param kwargs:
            :return:
        """
        term = response.meta.get('search_term')
        self.logger.info('analyzing : ' + term + ' ===============')

        data = response.json()
        result = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        if result == 'True':
            api_url = f"https://completion.amazon.com/api/2017/suggestions?limit=11&prefix={term}&suggestion-type=WIDGET&suggestion-type=KEYWORD&page-type=Search&alias=aps&site-variant=desktop&version=3&event=onkeypress&wc=&lop=en_US&last-prefix=ceramic%20fire%20balls&avg-ks-time=7481&fb=1&mid=ATVPDKIKX0DER&plain-mid=1&client-info=search-ui"
            yield scrapy.Request(api_url, meta={'term': term},
                                 callback=self.parse_rule_1)
        else:
            self.logs[term]['Rule 5-9'] = f"Failed: {result}"
            self.skipped_list.remove(term)
            yield {term: f"Rule 5-9 Failed: {result}"}
            self.save_logs()

    def parse_rule_1(self, response, **kwargs):
        term = response.meta.get('term')
        try:
            data = json.loads(response.body)['suggestions']
        except:
            self.logger.info("Couldn't get any suggestion.")
            self.logs[term]['Rule 1'] = "Failed: Couldn't get any suggestion."
            self.skipped_list.remove(term)
            yield {term: "Rule 1 Failed: Couldn't get any suggestion."}
            self.save_logs()
            return

        suggestions = []
        if len(data) >= 3:
            matching_suggestions = []
            for suggestion in data:
                value = suggestion.get('value', '').lower()
                suggestions.append(value)
                if value and term in value:
                    matching_suggestions.append(value)

            if len(matching_suggestions) >= 2:
                self.logger.info(f"Rule 1 passed for term {term}.")
                self.logs[term]['Rule 1'] = 'Passed'
                url = f"https://www.amazon.com/s?k={term}"
                meta = {'term': term, 'suggestions': suggestions}

                self.logger.info(f"Scrapping about {term}...")

                yield scrapy.Request(url, meta=meta, callback=self.parse_rule_2, headers=HEADERS)

            else:
                self.logger.info(f"Term {term} failed in Rule 1. {term} contains less than 2 in a suggestion.")
                self.logs[term]['Rule 1'] = f'Failed: {term} contains less than 2 in a suggestion.'
                self.skipped_list.remove(term)
                yield {term: f'Rule 1 Failed: {term} contains less than 2 in a suggestion.'}
                self.save_logs()
                return

        else:
            self.logger.info(f"Term {term} failed in Rule 1. Suggestions are less than 3.")
            self.logs[term]['Rule 1'] = f'Failed: {term} suggestions are less than 3.'
            self.skipped_list.remove(term)
            yield {term: f'Rule 1 Failed: {term} suggestions are less than 3.'}
            self.save_logs()

    def parse_rule_2(self, response, **kwargs):
        term = response.meta.get('term')

        if response.status != 200:
            self.logger.info(
                f"Rule 2 failed for term {term}. Status code are {response.status}.")
            self.logs[term]['Rule 2'] = f'Rule 2 failed for term {term}. Status code are {response.status}.'
            yield {term: f'Rule 2 failed for term {term}. Status code are {response.status}.'}
            self.save_logs()
            return
        suggestions = response.meta.get('suggestions')
        # getting the total results of the result page using regex
        total_results = get_number_of_results(response.xpath('//span[contains(text(),"result")]/text()').get(''))
        if 0 < total_results <= 400:
            unique_urls = set()
            product_listing = []
            for product in response.xpath("//div[@data-cy='title-recipe' and not(contains(., 'Sponsored'))]"):
                bought_items = product.css("span.a-size-base:contains('bought')::text").get('')
                bought_value = ''
                if bought_items:
                    bought_value = bought_items.split()[0].rstrip('+')
                    bought_value = convert_abbreviated_number(bought_value)

                price = float(product.css(
                    "span.a-price > span.a-offscreen::text, span:contains('No featured offers available') + br +span.a-color-base::text").get(
                    '0').lstrip('$'))

                # TODO discover why we will have duplicate urls in the same result page!!!!!!!!!!!!!!!!

                url = product.css("h2 > a::attr(href)").get()
                if url in unique_urls:
                    continue
                unique_urls.add(url)
                product_listing.append({
                    "url": response.urljoin(url),
                    'name': product.css("h2 > a > span::text").get('').strip().lower(),
                    'bought_values': bought_value,
                    'price': price,
                    'monthly_sale': bought_value * price if bought_value and price else 0
                })

            if product_listing:
                # storing the data of all products in meta
                min_sale = minimum_total_sales_of_search_group_for_results(total_results)

                self.logs[term]['Rule 2'] = 'Passed'
                self.save_logs()
                prompt = RULES.get('RULE_3').format(term, suggestions).strip()

                yield scrapy.Request(
                    url=API_URL_GPT,
                    method='POST',
                    headers=GPT_HEADERS,
                    body=get_gpt_payload(prompt),
                    # passing all needed data to next method
                    meta={'term': term, 'total_results': total_results, 'min_sale': min_sale,
                          'searched_term': suggestions, 'data': {
                            'main_url': response.url,
                            'data': product_listing,
                            'next_page_url': response.css('a.s-pagination-next::attr(href)').get()
                        }},
                    callback=self.parse_rule_3
                )
        elif total_results > 400:
            self.logger.info(
                f"Rule 2 failed for term {term}. Total Items Results are more than 400.")
            self.logs[term]['Rule 2'] = f'Failed: {term} has more than 400 items'
            self.skipped_list.remove(term)
            yield {term: f'Rule 2 Failed: {term} has more than 400 items'}
            self.save_logs()
            return
        else:
            self.logger.info(
                f"Rule 2 failed for term {term}. No Total Results are found.")
            self.logs[term]['Rule 2'] = f'Failed: {term}, No Total Results are found'
            self.skipped_list.remove(term)
            yield {term: f'Rule 2 Failed: {term}, No Total Results are found'}
            self.save_logs()
            return

    def parse_rule_3(self, response, **kwargs):
        """
        Process and verify Rule 3.1 compliance for a given search term using GPT responses.

        Steps:
        1. Parse the response from GPT to obtain the 'group term'.
        2. Extract the search term and product listings from the response metadata.
        3. Check the first 15 product titles to see if they match the 'group term'.
        4. If any product title does not match, Rule 3.1 succeeds and further processing continues.
        5. If all product titles match, Rule 3.1 fails, indicating more than 15 relevant items are found.
        6. If Rule 3.1 succeeds, proceed to Rule 3.2.

        Parameters:
        - response: The response object containing data from GPT and the product listings.
        - **kwargs: Additional keyword arguments (not used in this function).

        Key Variables:
        - group_term: A term representing a group of listings that match the search term.
        - term: The original search term.
        - product_listing: List of product titles returned for the search term.
        - prompt: The formatted prompt sent to GPT for validation of each product title.
        - parse_result: Boolean flag indicating if Rule 3.1 was successful or not.

        Exception Handling:
        - Logs and handles errors encountered during parsing of GPT response or requests to GPT.

        Usage:
        - This function is used in the context of a Scrapy spider to process and validate search term relevance based on GPT's analysis.
        """
        try:
            gpt_data = response.json()
            group_term = gpt_data.get('choices', [{}])[0].get('message', {}).get('content', '')
        except Exception as e:
            self.logger.error(f"Error parsing GPT response: {e}")
            return
        term = response.meta.get('term')
        meta = response.meta.copy()
        data = response.meta.get('data')
        product_listing = data['data']

        try:
            parse_result = False
            for product in product_listing[:15]:
                # Formatting the RULE_3_1 with the joined string
                prompt = RULES.get('RULE_3_1').format(product['name'], group_term).strip()
                response = requests.post(API_URL_GPT, headers=GPT_HEADERS, data=get_gpt_payload(prompt))
                gpt_response = response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
                if gpt_response == 'False':
                    self.logger.info(
                        f"Rule 3 1 success for term {group_term}.")
                    self.logs[term]['Rule 3 1'] = f'Success: {group_term}.'
                    self.save_logs()
                    parse_result = True
                    break

            if not parse_result:
                self.logger.info(
                    f"Rule 3 1 failed for term {group_term}. There are product lists more than 15 with the same topic.")
                self.logger.info(f"Prompt: {prompt}")
                self.logs[term][
                    'Rule 3'] = f'Failed: {group_term}. There are product lists more than 15 with the same topic.'
                self.skipped_list.remove(group_term)
                yield {
                    group_term: f'Rule 3 Failed: {group_term}. There are product lists more than 15 with the same topic.'}
                self.save_logs()
                return

        except requests.RequestException as e:
            self.logger.info(f"Request failed: {e}")
            return

        index = 0
        meta['name_index'] = index
        meta['group_term'] = group_term
        # meta['proxy'] = random.choice(PROXIES)

        prompt = RULES.get('RULE_3_2').format(group_term, product_listing[index]['name']).strip()
        yield scrapy.Request(
            url=API_URL_GPT,
            method='POST',
            headers=GPT_HEADERS,
            body=get_gpt_payload(prompt),
            meta=meta,
            callback=self.parse_rule_3_2
        )

    def parse_rule_3_2(self, response, **kwargs):
        try:
            gpt_data = response.json()
            result = gpt_data.get('choices', [{}])[0].get('message', {}).get('content', '')
        except:
            return

        term = response.meta.get('term')
        data = response.meta.get('data')
        group_term = response.meta.get('group_term')
        product_listing = data['data']
        index = response.meta.get('name_index') + 1

        if (result == "False") or (len(product_listing) < 15):
            term = response.meta.get('term')
            total_results = response.meta.get('total_results')
            min_sale = response.meta.get('min_sale')
            data = response.meta.get('data')
            product_listing = data['data']
            # SEARCH GROUP COMPLETED
            updated_data = [d for d in product_listing if d['price'] < 400]

            if len(updated_data) == 0:
                next_page_url = data.get('next_page_url')
                if not next_page_url:
                    self.logs[term]['Rule 3'] = f'Failed: {term} have no item < 400 price'
                    self.skipped_list.remove(term)
                    yield {term: f"f'Rule 3 Failed: {term} have no item < 400 price'"}
                    self.save_logs()
                    return
                else:
                    next_page_url = urljoin(BASE_URL, next_page_url)
                    listing_meta = {'term': term, 'total_results': total_results, 'min_sale': min_sale,
                                    'group_term': group_term, 'total_monthly_sale': 0}
                    yield scrapy.Request(next_page_url, meta=listing_meta, callback=self.parse_product_listing)
                    return

            total_monthly_sale = sum([d['monthly_sale'] for d in updated_data if d['monthly_sale'] > 0])

            updated_data_dict = {
                'main_url': data.get('main_url'),
                'data': updated_data,
                'next_page_url': data.get('next_page_url')

            }

            url = updated_data[0]['url']
            meta = {'term': term, 'total_results': total_results, 'min_sale': min_sale,
                    'group_term': group_term, 'data': updated_data_dict, 'index': 0,
                    'total_monthly_sale': total_monthly_sale}
            yield scrapy.Request(url, callback=self.parse_product_details_page, meta=meta)

            return
        elif index < len(product_listing[:15]):
            meta = response.meta.copy()
            meta['name_index'] = index
            meta['proxy'] = random.choice(PROXIES)
            prompt = RULES.get('RULE_3_2').format(group_term, product_listing[index]['name']).strip()
            yield scrapy.Request(
                url=API_URL_GPT,
                method='POST',
                headers=GPT_HEADERS,
                body=get_gpt_payload(prompt),
                meta=meta,
                callback=self.parse_rule_3_2
            )
        else:
            self.logs[term]['Rule 3'] = f'Failed: {term} does not match with consecutive 15 items.'
            self.skipped_list.remove(term)
            yield {term: f'Rule 3 Failed: {term} does not match with consecutive 15 items.'}
            self.save_logs()
            return

    def parse_product_details_page(self, response, **kwargs):
        if response.status != 200:
            pass
        # Extract data from response meta
        data = response.meta.get('data')
        index = response.meta.get('index')
        term = response.meta.get('term')
        total_results = response.meta.get('total_results')
        min_sale = response.meta.get('min_sale')
        group_term = response.meta.get('group_term')
        total_monthly_sale = response.meta.get('total_monthly_sale', 0)
        bundle_check = bool(response.css('div#bundleV2_feature_div > div.a-row * div.bundle-comp-title > a'))

        if bundle_check and not response.meta.get('bundle', False):
            # Process bundle URLs if present
            bundle_urls = response.css(
                'div#bundleV2_feature_div > div.a-row * div.bundle-comp-title > a::attr(href)').getall()
            for bundle_url in bundle_urls:
                meta = {'term': term, 'total_results': total_results, 'min_sale': min_sale,
                        'group_term': group_term, 'data': data, 'index': index,
                        'total_monthly_sale': total_monthly_sale, 'bundle': True}
                yield response.follow(bundle_url, meta=meta, callback=self.parse_product_details_page)
        else:
            # Extract product details
            product = data['data'][index]
            try:
                price = product['price'] or int(
                    response.css('span.aok-offscreen::text').get('').strip().lstrip('$').replace(
                        ',', '')) or 0
            except:
                price = 0
            if product['monthly_sale'] == 0:
                rank_subcate_1 = response.css("th:contains('Best Sellers Rank') ~ td span > span::text").get('').rstrip(
                    '(').split(' in ')

                if len(rank_subcate_1) < 2:
                    rank_subcate_1 = ''.join(
                        response.css('span.a-list-item:contains("Best Sellers Rank") ::text').getall()).replace(
                        'Best Sellers Rank:', '').strip().split('(')[0].strip().split(' in ')

                rank_subcate_2 = ''.join(response.css(
                    "th:contains('Best Sellers Rank') ~ td span > span + br + span ::text").getall()).rstrip('(').split(
                    ' in ')

                if len(rank_subcate_2) < 2:
                    rank_subcate_2 = ''.join(''.join(response.css(
                        'span.a-list-item:contains("Best Sellers Rank") > ul >li > span.a-list-item ::text').getall())).split(
                        ' in ')

                categories = [category.strip() for category in [rank_subcate_1[-1], rank_subcate_2[-1]]]
                ranks = [get_rank(rank.replace(',', '').strip('#')) for rank in
                         [rank_subcate_1[0].strip(), rank_subcate_2[0].strip()]]

                monthly_sales = []
                for category, rank in zip(categories, ranks):
                    if class_for_sales_rank.check_if_cat_exits(category):
                        rank_data = class_for_sales_rank.get_sales_cat(rank, category)
                        monthly_sales.append(rank_data["sales"] * int(price))

                if monthly_sales:
                    data['data'][index]['monthly_sale'] = monthly_sale = min(monthly_sales) if len(
                        monthly_sales) > 1 else \
                        monthly_sales[0]
                else:
                    data['data'][index]['monthly_sale'] = monthly_sale = 0

                total_monthly_sale += monthly_sale

            data['data'][index]['brand'] = response.css('td:contains("Brand") + td > span::text').get(
                '').strip() or response.css(
                'a#bylineInfo::text').get('').replace('Visit the', '').replace('Store', '').strip()

            if response.css('span:contains("a-color-price")'):
                data['data'].pop(index)

            # Move to the next product or process results if all products have been processed

            if index < len(data['data']) - 1:
                index += 1
                url = data['data'][index]['url']
                meta = {'term': term, 'total_results': total_results, 'min_sale': min_sale,
                        'group_term': group_term, 'data': data, 'index': index,
                        'total_monthly_sale': total_monthly_sale}

                yield response.follow(url, callback=self.parse_product_details_page, meta=meta)

            elif total_monthly_sale >= min_sale:
                self.logs[term]['Rule 3'] = f"Passed"
                self.save_logs()
                prompt = RULES.get('RULE_4').format(term).strip()
                payload_data = get_gpt_payload(prompt)
                yield scrapy.Request(
                    url=API_URL_GPT,
                    method='POST',
                    headers=GPT_HEADERS,
                    body=json.dumps(payload_data),
                    meta={'term': term, 'data': data},
                    callback=self.parse_rule_4
                )

            else:
                # Process the next page or finish processing if all products have been processed
                index += 1
                if index >= len(data['data']):
                    next_page_url = data.get('next_page_url')
                    if next_page_url:
                        meta = {'term': term, 'total_results': total_results, 'min_sale': min_sale,
                                'group_term': group_term, 'detail': True, 'total_monthly_sale': total_monthly_sale,
                                'data': data}
                        yield response.follow(next_page_url, callback=self.parse_product_listing, meta=meta)
                    else:
                        self.logs[term]['Rule 3'] = f"Failed: {term} doesn't match with min monthly sale."
                        self.skipped_list.remove(term)
                        yield {term: f"Rule 3 Failed: {term} doesn't match with min monthly sale."}
                        self.save_logs()
                        return False

    def parse_product_listing(self, response, **kwargs):
        if response.status != 200:
            pass
        term = response.meta.get('term')
        data = response.meta.get('data', {})
        group_term = response.meta.get('group_term')
        min_sale = response.meta.get('min_sale')
        total_results = response.meta.get('total_results')
        total_monthly_sale = response.meta.get('total_monthly_sale')

        unique_urls = set()
        product_listing_1 = data.get('data', [])
        product_listing_2 = []
        for product in response.css(
                'div[class="a-section a-spacing-small puis-padding-left-small puis-padding-right-small"],  div[data-csa-c-type="item"]'):
            if product.css('span:contains("Sponsored")'):
                continue

            bought_items = product.css("span.a-size-base:contains('bought')::text").get('')
            bought_value = ''
            if bought_items:
                bought_value = bought_items.split()[0].rstrip('+')
                bought_value = convert_abbreviated_number(bought_value)

            price = float(product.css(
                "span.a-price > span.a-offscreen::text, span:contains('No featured offers available') + br +span.a-color-base::text").get(
                '0').lstrip('$'))

            url = product.css("h2 > a::attr(href)").get()
            if url in unique_urls:
                continue

            unique_urls.add(url)
            product_listing_2.append({
                "url": response.urljoin(url),
                'name': product.css("h2 > a > span::text").get('').strip().lower(),
                'bought_values': bought_value if bought_value else '',
                'price': price,
                'monthly_sale': bought_value * price if bought_value and price else 0
            })

        updated_data = [d for d in product_listing_2 if d['price'] < 400]

        if len(updated_data) == 0:
            next_page_url = response.css('a.s-pagination-next::attr(href)').get()
            if not next_page_url:
                self.logs[term]['Rule 3'] = f'Failed: {term} have no item < 400 price'
                self.skipped_list.remove(term)
                yield {term: f"f'Rule 3 Failed: {term} have no item < 400 price'"}

                self.save_logs()
                return
            else:
                next_page_url = urljoin(BASE_URL, next_page_url)

                listing_meta = {'term': term, 'total_results': total_results, 'min_sale': min_sale,
                                'group_term': group_term, 'total_monthly_sale': 0, 'data': data,
                                'proxy': random.choice(PROXIES)}
                yield scrapy.Request(next_page_url, meta=listing_meta, callback=self.parse_product_listing)
                return

        new_total_monthly_sale = sum([d for d in updated_data if d['monthly_sale']])
        total_monthly_sale += new_total_monthly_sale
        product_listing = product_listing_1 + updated_data
        index = len(product_listing_1)
        if product_listing:
            updated_data_dict = {
                'main_url': response.url,
                'data': product_listing,
                'next_page_url': response.css('a.s-pagination-next::attr(href)').get()
            }
            url = updated_data[0]['url']
            meta = {'term': term, 'total_results': total_results, 'min_sale': min_sale,
                    'group_term': group_term, 'data': updated_data_dict, 'index': index,
                    'detail': True, 'total_monthly_sale': total_monthly_sale
                    }
            yield response.follow(url, callback=self.parse_product_details_page, meta=meta)

    def parse_rule_4(self, response, **kwargs):
        term = response.meta.get('term')
        try:
            gpt_data = response.json()
            result = gpt_data.get('choices', [{}])[0].get('message', {}).get('content', '')
        except:
            return

        if result == 'True':
            data = response.meta.get('data')
            products = data['data']
            brands = {}
            for product in products:
                brand = product.get('brand', '')
                if not brand:
                    continue
                if brand not in brands.keys():
                    brands[brand] = product['monthly_sale']
                else:
                    brands[brand] += product['monthly_sale']

            len_brands = len(brands.keys())
            if len_brands > 1:
                for brand, monthly_sale in brands.items():
                    if monthly_sale >= 100:
                        self.logs[term]['Rule 4'] = f"Passed."
                        self.skipped_list.remove(term)
                        yield {term: f"Passed."}
                        self.save_logs()
                        return
                    else:
                        self.logs[term]['Rule 4'] = f"Failed: {term} has no brands > $100 sale."
                        self.skipped_list.remove(term)
                        yield {term: f"Rule 4 Failed: {term} has no brands > $100 sale."}
                        self.save_logs()
                        return
            else:
                self.logs[term]['Rule 4'] = f"Failed: {term} has {len_brands} brands."
                self.skipped_list.remove(term)
                yield {term: f"Rule 4 Failed: {term} has {len_brands} brands."}
                self.save_logs()
                return
        else:
            self.logs[term]['Rule 4'] = f"Passed."
            self.skipped_list.remove(term)
            yield {term: f"Passed."}
            self.save_logs()
            return

    def save_logs(self):
        with open('inputs/rule_logs.json', 'w') as f:
            json.dump(self.logs, f, indent=4)

    def close(self, spider, reason):
        with open('inputs/skipped.json', 'w') as f:
            json.dump(list(self.skipped_list), f, indent=4)


if __name__ == "__main__":
    with open('inputs/config.json', 'r') as json_file:
        config_data = json.load(json_file)

    HEADERS = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "max-age=0",
        "device-memory": "8",
        "downlink": "6.85",
        "dpr": "1.5",
        "ect": "4g",
        # "referer": "https://www.amazon.com/s?k=stanley&crid=PVDMUJUCJK7N&sprefix=stanley%2Caps%2C334&ref=nb_sb_noss_1",
        "rtt": "200",
        "sec-ch-device-memory": "8",
        "sec-ch-dpr": "1.5",
        "sec-ch-ua": "\"Google Chrome\";v=\"123\", \"Not:A-Brand\";v=\"8\", \"Chromium\";v=\"123\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-ch-ua-platform-version": "\"10.0.0\"",
        "sec-ch-viewport-width": "1442",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "viewport-width": "1442"
    }
    GPT_HEADERS = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {config_data.get("GPT_API_KEY")}'
    }
    RULES = config_data.get('RULES')
    API_URL_GPT = config_data.get('API_URL_GPT')
    BASE_URL = config_data.get('BASE_URL')

    class_for_sales_rank = run_class()
    PROXIES = get_proxies()

    local_setting = get_project_settings()
    local_setting['FEED_FORMAT'] = 'json'
    local_setting['FEED_URI'] = f"outputs/final_logs.json"
    local_setting['ROBOTSTXT_OBEY'] = False
    # local_setting['RETRY_TIMES'] = config_data.get('RETRY_TIME')
    # local_setting['RETRY_HTTP_CODES'] = [500, 502, 503, 504, 400, 403, 404, 408]
    # local_setting['ROTATING_PROXY_LIST_PATH'] = config_data.get('PROXIES_FILE_PATH')
    local_setting['DOWNLOADER_MIDDLEWARES'] = {
        #     'rotating_proxies.middlewares.RotatingProxyMiddleware': 610,
        #     'rotating_proxies.middlewares.BanDetectionMiddleware': 620,
        'middlewares.handle_middleware.HandleMiddleware': 543,
        # 'middlewares.proxy_retry_middleware.ProxyRetryMiddleware': 543
    }

    local_setting['HTTPERROR_ALLOW_ALL'] = True
    local_setting['DOWNLOAD_TIMEOUT'] = 1800
    local_setting[
        'USER_AGENT'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82 Safari/537.36'
    local_setting['LOG_LEVEL'] = 'DEBUG'
    local_setting['CONCURRENT_REQUESTS'] = config_data.get('CONCURRENT_REQUESTS')
    local_setting['CUSTOM_CONFIG_DATA'] = config_data
    local_setting['PROXIES'] = PROXIES

    process = CrawlerProcess(local_setting)
    crawler = process.create_crawler(AmazonSpider)
    process.crawl(crawler)
    process.start()

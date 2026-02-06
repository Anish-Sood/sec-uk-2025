import requests
from bs4 import BeautifulSoup
import os
import csv
import ddddocr
import re
BASE_URL = "https://secvotersearch.uk.gov.in"
SEARCH_URL = "https://secvotersearch.uk.gov.in/searchvoterchecklist"
ocr = ddddocr.DdddOcr()

def sanitize(name):
    """Removes illegal characters from filenames (windows/linux safe)."""
    # Replace / and \ with - to keep structure info if needed, remove others
    name = name.replace("/", "-").replace("\\", "-")
    return re.sub(r'[*:?"<>|]', "", name).strip()

def get_hidden_fields(soup):
    payload = {}
    for tag in soup.find_all("input", type="hidden"):
        if tag.get("name"):
            payload[tag["name"]] = tag.get("value", "")
    return payload

def find_districts(soup):
    districts=[]
    select=soup.find("select", id="ContentPlaceHolder1_ddlDistrict")
    for option in select.find_all("option"):
        value=option.get("value")
        name=option.text.strip()
        if value != "0":
            districts.append({"district_code": value, "district_name": name})
    # print(districts)
    return districts

def find_blocks(soup):
    blocks=[]
    select=soup.find("select", id="ContentPlaceHolder1_ddlBlock")
    for option in select.find_all("option"):
        value=option.get("value")
        name=option.text.strip()
        if value != "0":
            blocks.append({"block_code": value, "block_name": name})
    # print(blocks)
    return blocks

def find_gps(soup):
    gps=[]
    select=soup.find("select", id="ContentPlaceHolder1_ddlGramPanchayat")
    for option in select.find_all("option"):
        value=option.get("value")
        name=option.text.strip()
        if value != "0":
            gps.append({"gp_code": value, "gp_name": name})
    # print(gps)
    return gps

def find_pollings(soup):
    pollings=[]
    select=soup.find("select", id="ContentPlaceHolder1_ddlPS")
    for option in select.find_all("option"):
        value=option.get("value")
        name=option.text.strip()
        if value != "0":
            pollings.append({"polling_code": value, "polling_name": name})
    # print(gps)
    return pollings

def solve_captcha(session, img_relative_url):
    full_url = BASE_URL + "/" + img_relative_url.lstrip("/")
    
    print(f"   Downloading Captcha: {full_url}...")
    resp = session.get(full_url)
    
    if resp.status_code == 200:
        # Pass image bytes directly to ddddocr
        res = ocr.classification(resp.content)
        print(f"   [ddddocr] Solved: {res}")
        return res.upper() # Site expects Uppercase
    else:
        print("   Failed to download captcha image.")
        return ""

def main():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    })

    print("1. page load ---")
    resp = s.get(SEARCH_URL)
    soup = BeautifulSoup(resp.text, "html.parser")
    payload = get_hidden_fields(soup)
    all_districts=find_districts(soup)
    # print(districts)
    # districts=[{'district_code': '045', 'district_name': 'अल्मोड़ा'}]
    # all_districts=districts
    for index, item in enumerate(all_districts):
        print(f"{index}: {item}")
    select = int(input("Select a valid index: "))
    districts=[]
    if 0 <= select < len(all_districts):
        districts.append(all_districts[select])
        print("new list", districts)
    else:
        print("Invalid index")

    for district in districts:
        print(district["district_code"])
        print(district["district_name"])
        print(f"IN {district['district_name']}")
        payload.update({
        "__EVENTTARGET": "ctl00$ContentPlaceHolder1$ddlDistrict",
        "ctl00$ContentPlaceHolder1$ddlDistrict": district["district_code"],
        "ctl00$ContentPlaceHolder1$ddlBlock": "0",
        "ctl00$ContentPlaceHolder1$ddlGramPanchayat": "0"
        })
        resp = s.post(SEARCH_URL, data=payload)
        soup = BeautifulSoup(resp.text, "html.parser")
        payload = get_hidden_fields(soup)
        blocks=find_blocks(soup)
        for block in blocks:
            print(f"IN {block['block_name']}")
            payload.update({
                "__EVENTTARGET": "ctl00$ContentPlaceHolder1$ddlBlock",
                "ctl00$ContentPlaceHolder1$ddlDistrict": district["district_code"],
                "ctl00$ContentPlaceHolder1$ddlBlock": block["block_code"],
                "ctl00$ContentPlaceHolder1$ddlGramPanchayat": "0"
            })
            resp = s.post(SEARCH_URL, data=payload)
            soup = BeautifulSoup(resp.text, "html.parser")
            payload = get_hidden_fields(soup)
            gps=find_gps(soup)
            for gp in gps:
                print(f"IN {gp['gp_name']}")
                gp_request_payload = payload.copy()
                gp_request_payload.update({
                    "__EVENTTARGET": "ctl00$ContentPlaceHolder1$ddlGramPanchayat",
                    "ctl00$ContentPlaceHolder1$ddlDistrict": district["district_code"],
                    "ctl00$ContentPlaceHolder1$ddlBlock": block["block_code"],
                    "ctl00$ContentPlaceHolder1$ddlGramPanchayat": gp["gp_code"]
                })
                
                resp = s.post(SEARCH_URL, data=gp_request_payload)
                soup = BeautifulSoup(resp.text, "html.parser")
                payload = get_hidden_fields(soup)

                

                pollings=find_pollings(soup)

                for polling in pollings:
                    print(f"IN {polling['polling_name']}")
                    retries = 5
                    attempt = 0
                    success = False
                    while attempt < retries and not success:
                        attempt += 1
                        if attempt > 1:
                            print(f"        attempt {attempt}/{retries}...")

                        try:
                            if attempt > 1:
                                resp = s.post(SEARCH_URL, data=gp_request_payload)
                                soup = BeautifulSoup(resp.text, "html.parser")
                                payload = get_hidden_fields(soup)
                    
                            current_payload = payload.copy()
                            
                            captcha_divs = soup.find_all("div", class_="captcha")
                            if len(captcha_divs) < 2:
                                print("        ! Search Captcha missing (Page Load Error).")
                                continue
                                
                            search_captcha_url = captcha_divs[1].find("img")["src"]
                            captcha_text = solve_captcha(s, search_captcha_url)
                            
                            current_payload.update({
                                "__EVENTTARGET": "",
                                "ctl00$ContentPlaceHolder1$ddlDistrict": district["district_code"],
                                "ctl00$ContentPlaceHolder1$ddlBlock": block["block_code"],
                                "ctl00$ContentPlaceHolder1$ddlGramPanchayat": gp["gp_code"],
                                "ctl00$ContentPlaceHolder1$ddlPS": polling["polling_code"],
                                "ctl00$ContentPlaceHolder1$txtCaptcha": captcha_text,
                                "ctl00$ContentPlaceHolder1$btnSubmit": "सर्च करें"
                            })
                            
                            search_resp = s.post(SEARCH_URL, data=current_payload, timeout=30)
                            
                            if "GridView1" not in search_resp.text:
                                continue 
                            
                            search_soup = BeautifulSoup(search_resp.text, "html.parser")
                            search_payload = get_hidden_fields(search_soup)
                            
                            if "ctl00$ContentPlaceHolder1$btnSubmit" in search_payload:
                                del search_payload["ctl00$ContentPlaceHolder1$btnSubmit"]

                            search_payload.update({
                                "__EVENTTARGET": "ctl00$ContentPlaceHolder1$GridView1$ctl02$lblFD",
                                "ctl00$ContentPlaceHolder1$ddlDistrict": district["district_code"],
                                "ctl00$ContentPlaceHolder1$ddlBlock": block["block_code"],
                                "ctl00$ContentPlaceHolder1$ddlGramPanchayat": gp["gp_code"],
                                "ctl00$ContentPlaceHolder1$ddlPS": polling["polling_code"],
                                "ctl00$ContentPlaceHolder1$txtCaptcha": captcha_text 
                            })
                            
                            modal_resp = s.post(SEARCH_URL, data=search_payload, timeout=30)
                            modal_soup = BeautifulSoup(modal_resp.text, "html.parser")
                            modal_payload = get_hidden_fields(modal_soup)
                            
                            modal_captcha_divs = modal_soup.find_all("div", class_="captcha")
                            if not modal_captcha_divs:
                                print("         Modal Captcha not found.")
                                continue 
                                
                            modal_captcha_url = modal_captcha_divs[0].find("img")["src"]
                            modal_captcha_text = solve_captcha(s, modal_captcha_url)
                            
                            modal_payload.update({
                                "__EVENTTARGET": "",
                                "ctl00$ContentPlaceHolder1$ddlDistrict": district["district_code"],
                                "ctl00$ContentPlaceHolder1$ddlBlock": block["block_code"],
                                "ctl00$ContentPlaceHolder1$ddlGramPanchayat": gp["gp_code"],
                                "ctl00$ContentPlaceHolder1$ddlPS": polling["polling_code"],
                                "ctl00$ContentPlaceHolder1$txtCaptcha1": modal_captcha_text,
                                "ctl00$ContentPlaceHolder1$btnFinalSubmit": "डाउनलोड करें"
                            })
                            
                            print("         Downloading pdf...")
                            pdf_resp = s.post(SEARCH_URL, data=modal_payload, stream=True, timeout=60)
                            
                            if pdf_resp.status_code == 200:
                                content_type = pdf_resp.headers.get('Content-Type', '')
                                if 'pdf' in content_type.lower() or 'octet-stream' in content_type.lower():
                                    
                                    clean_district = district['district_name']
                                    clean_block = block['block_name']
                                    clean_gp = gp['gp_name']
                                    
                                    save_folder = os.path.join("sec uk captcha/downloads", clean_district, clean_block, clean_gp)
                                    
                                    os.makedirs(save_folder, exist_ok=True)
                                    
                                    clean_filename = f"{polling['polling_name']}.pdf"
                                    full_path = os.path.join(save_folder, clean_filename)
                                    
                                    with open(full_path, 'wb') as f:
                                        for chunk in pdf_resp.iter_content(chunk_size=8192):
                                            f.write(chunk)
                                            
                                    print(f"        Saved: {full_path}")
                                    success = True 
                                else:
                                    print("        Download Failed: HTML returned ( Wrong Modal Captcha ig)")
                            else:
                                print(f"         HTTP Error {pdf_resp.status_code}")
                                
                        except requests.exceptions.RequestException as e:
                            print(f"         Network Error: {e}")
                    
                    if not success:
                        print(f"       GAVE UP on {polling['polling_name']}")
                        log = "sec uk captcha/failed_downloads.csv"
                        
                        file_exists = os.path.isfile(log)
                        
                        try:
                            with open(log, "a", encoding="utf-8", newline="") as f:
                                writer = csv.writer(f)
                                
                                if not file_exists:
                                    writer.writerow(["District Name", "Block Name", "GP Name", "PS Name", "Dist Code", "Block Code", "GP Code", "PS Code"])
                                
                                writer.writerow([district['district_name'],block['block_name'],gp['gp_name'],polling['polling_name'],district['district_code'],block['block_code'],gp['gp_code'],polling['polling_code']
                                ])
                                print(f"       logged to {log}")
                        except Exception as e:
                            print(f"      Error writing to log: {e}")
                            

if __name__ == "__main__":
    main()

        
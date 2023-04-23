import regex
import requests
from bs4 import BeautifulSoup, Tag


class Property:
    signature: str
    description: str = ""

    def __init__(self, section_tag: Tag):
        self.signature = section_tag.find_all(class_="tsd-signature")[0].text.replace("\n", "")

        descrip_p = section_tag.find_all(name="p")
        if len(descrip_p) > 0:
            self.description = descrip_p[0].text.replace("\n", "")

    @property
    def doc_string(self):
        return (f"\t/**\n"
                f"\t* {self.description}\n"
                f"\t*/\n"
                f"\t{self.signature}\n")


class Parameter:
    signature: str
    description: str
    name: str

    def __init__(self, li_tag: Tag):
        self.signature = li_tag.contents[1].text.replace("\n", "")
        self.description = li_tag.contents[3].text.replace("\n", "")
        self.name = regex.findall('^.*(?=:)', self.signature)[0]

    @property
    def doc_string(self):
        return f"\t* @param {self.name} {self.description}"


class Method:
    parameters: list[Parameter]
    return_signature: str
    return_description: str
    name: str
    description: str

    @property
    def signature(self) -> str:
        return f"{self.name}({', '.join(map(lambda param: param.signature, self.parameters))}): {self.return_signature}"

    @property
    def doc_string(self) -> str:
        param_docs = "".join(map(lambda param: param.doc_string + "\n", self.parameters))
        return (f"\t/** \n"
                f"\t* {self.description}\n"
                f"{param_docs}"
                f"\t* @return {self.return_description}\n"
                f"\t*/\n"
                f"\t{self.signature}\n")

    def __init__(self, section_tag: Tag, name=None):
        if not name:
            self.name = section_tag.contents[0].get("id")
        else:
            self.name = name
        tsd_description = section_tag.find_all(class_="tsd-description")[0]
        self.description = tsd_description.contents[1].contents[0].text
        self.return_description = tsd_description.contents[1].contents[3].text.replace("\n", "")
        self.return_signature = section_tag.contents[-1].contents[3].contents[5].text.replace("Returns ", "")

        param_list = section_tag.find_next(class_="tsd-parameter-list")
        self.parameters = []
        for param_tag in param_list.children:
            if isinstance(param_tag, Tag):
                self.parameters.append(Parameter(param_tag))


def parse_interface(soup: BeautifulSoup, declaration_signature: str):
    properties_header = soup.find_all(name="h2", string="Properties")[0]
    prop_section_parent: Tag = properties_header.parent
    prop_sections = prop_section_parent.find_all(name="section")

    properties = []
    for prop_section in prop_sections:
        properties.append(Property(prop_section))

    methods = []
    methods_header = soup.find_all(name="h2", string="Methods")
    if len(methods_header) > 1:
        methods_section_parent: Tag = methods_header.parent
        methods_sections = methods_section_parent.find_all(name="section")

        for methods_section in methods_sections:
            methods.append(Method(methods_section))

    properties_string = '\n'.join(map(lambda prop: prop.doc_string, properties))
    methods_string = '\n'.join(map(lambda prop: prop.doc_string, methods))

    return (f"{declaration_signature} {{\n"
            f"{properties_string} \n {methods_string}\n"
            f"}}")


def get_declaration_signature(url: str):
    splitted = url.replace(".html", "").split("/")

    if splitted[0] == "interfaces":
        object_type = "interface"
    elif splitted[0] == "types":
        object_type = "type"
    else:
        return None

    return f"{object_type} {splitted[-1].split('.')[-1]}"


def parse_type(soup: BeautifulSoup) -> str:
    type_declaration = soup.find_all(name="h4", string="Type declaration")
    signature = tsd_signature = soup.find_all(class_="tsd-signature")[0].text
    comments = soup.find_all(class_="tsd-comment tsd-typography")
    if len(comments) > 0:
        for comment in comments:
            comment_text = comment.text.replace("\n", "")
            if not comment.previous_sibling.previous_sibling:
                continue
            signature = signature.replace(comment.previous_sibling.previous_sibling.text + ";",
                                          (f"\t\n/**\n"
                                           f"\t* {comment_text}\n"
                                           f"\t*/\n"
                                           f"\t{comment.previous_sibling.previous_sibling.text}\n")).replace("\xa0", "")
        signature = signature.replace(":", " =", 1)
        signature = "type " + signature

        methods = soup.find_all(name="h5")
        for method in methods:
            if "function" not in method.text:
                continue
            name = method.text.split(":")[0]
            method_object = Method(method.parent, name)
            signature = regex.sub(f"({name}).*(?<=;)", method_object.doc_string, signature)

        return signature

    tsd_signature = soup.find_all(class_="tsd-signature")[0].text.replace(":", " =", 1)
    return f"type {tsd_signature}".replace("\xa0", "")


query_url = "https://www.warcraftlogs.com/scripting-api-docs/warcraft/index.html"
data = requests.get(query_url)
page_content = BeautifulSoup(data.content, "html.parser")

all_links = page_content.find_all(name="a")

with open("out/RpgLogs.d.ts", "w") as f:
    f.write("// This definition for the RpgLogs API is is auto generated from https://www.warcraftlogs.com/scripting-api-docs/warcraft/index.html\n"
            "// it is not officially supported by WarcraftLogs")
    for link in all_links:
        href = link.get("href")
        if href:
            decla_signature = get_declaration_signature(href)
            if not decla_signature:
                continue

            target_url = f"https://www.warcraftlogs.com/scripting-api-docs/warcraft/{href}"
            print(target_url)
            page_data = BeautifulSoup(requests.get(target_url).content, "html.parser")

            declaration = ""
            print(decla_signature)
            if "interface" in decla_signature:

                declaration = parse_interface(page_data, decla_signature)
            if "type" in decla_signature:
                declaration = parse_type(page_data)

            f.write("export " + declaration + "\n")

    f.write(f"\n/**\n"
            f"/* MANUAL ADDITION: This type is undocumented, but see This type is undocumented see {{@link ChartComponent.props}} for further information\n"
            f"*/\n"
            f"export type ChartComponentProps = object")


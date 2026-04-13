import pandas as pd


def process_fiori_excel(file_path):
    df = pd.read_csv(file_path)

    apps = []

    for _, row in df.iterrows():

        description = str(row.get("GTMAppDescription", "")).strip()

        # 🔥 Skip useless generic SAP GUI apps (VERY IMPORTANT)
        if "SAP GUI for HTML transaction" in description:
            continue

        app = {
            "app_id": str(row.get("fioriId", "")).strip(),
            "title": str(row.get("AppName", "")).strip(),
            "description": description,
            "business_role": str(row.get("RoleName", "")).strip(),
            "product": str(row.get("ProductCategory", "")).strip(),
            "app_type": str(row.get("ApplicationType", "")).strip(),
        }

        # skip empty rows
        if app["title"]:
            apps.append(app)

    return apps
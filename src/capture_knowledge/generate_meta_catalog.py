import yaml
import git
import os
import json
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path
from slugify import slugify

class MetaCatalogGenerator:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = self.load_config()
        self.meta_catalog = []

    def load_config(self):
        with open(self.config_path, 'r') as file:
            return yaml.safe_load(file)

    def clone_or_pull_repo(self, repo_url, local_path):
        if os.path.exists(local_path):
            repo = git.Repo(local_path)
            origin = repo.remotes.origin
            origin.pull()
        else:
            git.Repo.clone_from(repo_url, local_path)

    def process_catalog(self, catalog):
        repo_url = catalog['repo_url']
        local_path = f"./repos/{catalog['name']}"
        self.clone_or_pull_repo(repo_url, local_path)

        db_path = Path(local_path) / 'album_catalog_index.db'
        if not db_path.exists():
            print(f"Database not found for catalog: {catalog['name']}")
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM solution")
        solutions = cursor.fetchall()

        for solution in solutions:
            solution_path = Path(local_path) / 'solutions' / solution[1] / solution[2] / 'solution.yml'
            if solution_path.exists():
                with open(solution_path, 'r') as file:
                    solution_data = yaml.safe_load(file)
                
                solution_dict = {
                    'catalog_name': catalog['name'],
                    'catalog_url': repo_url,
                    'solution_id': solution[0],
                    'group': solution[1],
                    'name': solution[2],
                    'version': solution[4],
                    'title': solution_data.get('title', solution[3]),
                    'description': solution_data.get('description', solution[5]),
                    'date': solution_data.get('timestamp', datetime.now().strftime('%Y-%m-%d')),
                    'args': solution_data.get('args', []),
                    'citation': solution_data.get('cite', []),
                    'authors': solution_data.get('solution_creators', []),
                    'license': solution_data.get('license', ''),
                    'tags': solution_data.get('tags', []),
                }
                self.meta_catalog.append(solution_dict)
                self.create_markdown_file(solution_dict, local_path)

        conn.close()

    def create_markdown_file(self, solution, local_path):
        content_dir = Path("content/solutions")
        content_dir.mkdir(parents=True, exist_ok=True)

        catalog_slug = slugify(solution['catalog_name'])
        group_slug = slugify(solution['group'])
        name_slug = slugify(solution['name'])
        version_slug = slugify(solution['version'])

        file_path = content_dir / catalog_slug / group_slug / name_slug / f"{version_slug}.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w") as f:
            f.write("---\n")
            f.write(f"title: \"{solution['title']}\"\n")
            f.write(f"date: {solution['date']}\n")
            f.write(f"catalog: \"{solution['catalog_name']}\"\n")
            f.write(f"group: \"{solution['group']}\"\n")
            f.write(f"name: \"{solution['name']}\"\n")
            f.write(f"version: \"{solution['version']}\"\n")
            f.write(f"catalog_url: \"{solution['catalog_url']}\"\n")
            f.write(f"description: \"{solution['description']}\"\n")
            if solution['authors']:
                f.write(f"authors: {json.dumps(solution['authors'])}\n")
            if solution['license']:
                f.write(f"license: \"{solution['license']}\"\n")
            if solution['tags']:
                f.write(f"tags: {json.dumps(solution['tags'])}\n")
            f.write("---\n\n")
            f.write(solution['description'] + "\n\n")

            if solution['args']:
                f.write("## Arguments\n\n")
                for arg in solution['args']:
                    f.write(f"- **{arg['name']}** ({arg['type']}): {arg['description']}\n")
                f.write("\n")

            if solution['citation']:
                f.write("## Citation\n\n")
                for cite in solution['citation']:
                    f.write(f"- {cite.get('text', '')}\n")
                    if 'url' in cite:
                        f.write(f"  URL: {cite['url']}\n")
                f.write("\n")

        self.fetch_static_files(solution, local_path)

    def fetch_static_files(self, solution, local_path):
        catalog_slug = solution['catalog_name'].replace('.', '-')
        group_slug = slugify(solution['group'])
        name_slug = slugify(solution['name'])
        version_slug = solution['version'].replace('.', '-')

        # Fetch and save cover image
        cover_image_path = Path(local_path) / 'solutions' / solution['group'] / solution['name'] / 'cover.png'
        print(f"Debug: Checking for cover image at {cover_image_path}")
        if cover_image_path.exists():
            dest_image_path = Path("static/images/solutions") / catalog_slug / group_slug / name_slug / f"{version_slug}-cover.png"
            dest_image_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(str(cover_image_path), str(dest_image_path))
            print(f"Debug: Copied cover image from {cover_image_path} to {dest_image_path}")
        else:
            print(f"Debug: Cover image not found for {solution['catalog_name']}:{solution['group']}:{solution['name']}:{solution['version']}")

        # Fetch and save other static files (e.g., additional images, data files)
        static_dir = Path(local_path) / 'solutions' / solution['group'] / solution['name'] / 'static'
        if static_dir.exists():
            dest_static_dir = Path("static/files/solutions") / catalog_slug / group_slug / name_slug / version_slug
            dest_static_dir.mkdir(parents=True, exist_ok=True)
            for file in static_dir.glob('**/*'):
                if file.is_file():
                    relative_path = file.relative_to(static_dir)
                    dest_file = dest_static_dir / relative_path
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(str(file), str(dest_file))

    def generate_meta_catalog(self):
        for catalog in self.config['catalogs']:
            self.process_catalog(catalog)

    def save_meta_catalog(self, output_path):
        with open(output_path, 'w') as file:
            json.dump(self.meta_catalog, file, indent=2)

if __name__ == "__main__":
    generator = MetaCatalogGenerator('config.yaml')
    generator.generate_meta_catalog()
    generator.save_meta_catalog('meta_catalog.json')
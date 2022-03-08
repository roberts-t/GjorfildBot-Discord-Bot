
class Champion:

    def __init__(self, champion_json):
        if champion_json is None:
            self.version = self.id = self.key = self.name = self.title = self.blurb = self.image_file = self.types = "Unknown"
        else:
            self.version = champion_json['version']
            self.id = champion_json['id']
            self.key = champion_json['key']
            self.name = champion_json['name']
            self.title = champion_json['title']
            self.blurb = champion_json['blurb']
            self.image_file = champion_json['image']['full']
            self.types = champion_json['tags']

    def get_id_name(self):
        return self.id

    def get_key(self):
        return self.key

    def get_name(self):
        return self.name

    def get_title(self):
        return self.title

    def get_description(self):
        return self.blurb

    def get_icon_filename(self):
        return self.image_file

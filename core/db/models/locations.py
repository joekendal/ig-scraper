import os, csv
from neomodel import (StructuredNode, StringProperty, RelationshipTo,
                      RelationshipFrom, FloatProperty, IntegerProperty)


class Country(StructuredNode):
    iso_code = StringProperty(unique_index=True)
    name = StringProperty()

    cities = RelationshipFrom("City", "IS_IN")
    provinces = RelationshipFrom("Province", "IS_IN")

    @staticmethod
    def get_by_iso(code):
        return Country.nodes.first_or_none(iso_code=code)


class Province(StructuredNode):
    iso_code = StringProperty()
    name = StringProperty()

    country = RelationshipTo("Country", "IS_IN")
    cities = RelationshipFrom("City", "IS_IN")

    @staticmethod
    def get_by_iso_and_country(iso_code, country_code):
        country = Country.nodes.first_or_none(iso_code=country_code)
        if not country: return None
        result = country.provinces.search(iso_code=iso_code)
        if result: return result[0]
        return None


class City(StructuredNode):
    name = StringProperty()
    name_ascii = StringProperty()

    latitude = FloatProperty()
    longitude = FloatProperty()

    population = IntegerProperty()

    country = RelationshipTo("Country", "IS_IN")
    province = RelationshipTo("Province", "IS_IN")
    users = RelationshipFrom("User", "MENTIONED")

    @staticmethod
    def get_by_name_and_geoposition(name, latitude, longitude):
        return City.nodes.first_or_none(name=name, latitude=latitude, longitude=longitude)


if __name__ == "__main__":
    def main():
        with open('cities15000.txt') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter='\t')
            line_count = 0
            for row in csv_reader:
                if line_count == 0:
                    line_count += 1
                else:
                    geonameid = row[0]
                    name = row[1]
                    ascii_name = row[2]
                    alternatenames = row[3]
                    latitude = float(row[4])
                    longitude = float(row[5])
                    feature_class = row[6]
                    feature_code = row[7]
                    country_code = row[8]
                    cc2 = row[9]
                    admin1_code = row[10]
                    admin2_code = row[11]
                    admin3_code = row[12]
                    admin4_code = row[13]
                    population = row[14]
                    elevation = row[15]
                    dem = row[16]
                    timezone = row[17]
                    modification_date = row[18]

                    if not City.get_by_name_and_geoposition(name, latitude, longitude):
                        new_city = City(name=name, name_ascii=ascii_name,
                                        latitude=latitude, longitude=longitude,
                                        population=population).save()
                        province = Province.get_by_iso_and_country(admin1_code, country_code)
                        if not province:
                            province = Province(iso_code=admin1_code).save()
                            country = Country.get_by_iso(country_code)
                            if not country:
                                country = Country(iso_code=country_code).save()
                            province.country.connect(country)
                        else:
                            province = province[0]
                        new_city.province.connect(province)
                        output = f"""
        {line_count} / 24336
                        City:
                            name:   {name}
                            name_ascii: {ascii_name}
                            location: ({latitude}, {longitude})
                            population: {population}
                        Country:
                            iso:   {country_code}
                        Province:
                            iso:   {admin1_code}
                        """
                        print(output)

                    line_count += 1
            print(f'Processed {line_count} lines.')

    main()

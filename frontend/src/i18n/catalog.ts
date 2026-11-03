import { locale, localeTag, type Locale } from './index'

type Translation = { name?: string; description?: string }
type Translations = Partial<Record<Locale, Translation>>
type DishContent = { name: string; description?: string; translations?: Translations; weight?: string; calories?: string; proteins?: string; fats?: string; carbohydrates?: string }

// Seed content only: exact source matching ensures an administrator's own edits stay visible.
// New dishes use the optional translations saved by the administrator, with the original as fallback.
const dishes: [string, string, [string, string], [string, string], [string, string], [string, string]][] = [
  ['Spring Salad', 'Young greens, radish, cucumber and herb dressing.', ['Весняний салат', 'Молода зелень, редиска, огірок і заправка з травами.'], ['Salade printanière', 'Jeunes pousses, radis, concombre et vinaigrette aux herbes.'], ['Ensalada de primavera', 'Brotes tiernos, rábanos, pepino y aliño de hierbas.'], ['Frühlingssalat', 'Junge Blattsalate, Radieschen, Gurke und Kräuterdressing.']],
  ['Fresh Strawberry Mint Salad', 'Strawberries, mint, feta and balsamic glaze.', ['Салат із полуницею та м’ятою', 'Полуниця, м’ята, фета й бальзамічний соус.'], ['Salade de fraises à la menthe', 'Fraises, menthe, feta et crème de balsamique.'], ['Ensalada de fresas y menta', 'Fresas, menta, queso feta y crema balsámica.'], ['Erdbeer-Minz-Salat', 'Erdbeeren, Minze, Feta und Balsamico-Creme.']],
  ['Avocado Pine Nut Bowl', 'Avocado, quinoa, pine nuts and lime.', ['Боул з авокадо та кедровими горішками', 'Авокадо, кіноа, кедрові горішки й лайм.'], ['Bowl à l’avocat et aux pignons', 'Avocat, quinoa, pignons de pin et citron vert.'], ['Bol de aguacate y piñones', 'Aguacate, quinoa, piñones y lima.'], ['Avocado-Bowl mit Pinienkernen', 'Avocado, Quinoa, Pinienkerne und Limette.']],
  ['Roasted Sweet Potato & Lentil Salad', 'Warm lentils with roasted sweet potato and tahini.', ['Салат із печеним бататом і сочевицею', 'Тепла сочевиця з печеним бататом і тахіні.'], ['Salade de lentilles et patate douce rôtie', 'Lentilles tièdes, patate douce rôtie et tahini.'], ['Ensalada de lentejas y boniato asado', 'Lentejas templadas con boniato asado y tahini.'], ['Linsensalat mit gerösteter Süßkartoffel', 'Warme Linsen mit gerösteter Süßkartoffel und Tahini.']],
  ['Khachapuri Adjaruli', 'Boat-shaped bread with sulguni cheese, egg and butter.', ['Хачапурі по-аджарськи', 'Хачапурі у формі човника із сулугуні, яйцем і вершковим маслом.'], ['Khatchapouri adjarien', 'Pain en forme de barque garni de fromage soulgouni, d’un œuf et de beurre.'], ['Jachapuri adjariano', 'Pan en forma de barca con queso sulguni, huevo y mantequilla.'], ['Adscharisches Chatschapuri', 'Brot in Schiffchenform mit Sulguni-Käse, Ei und Butter.']],
  ['Chicken Shkmeruli', 'Roasted chicken in creamy garlic sauce.', ['Курка шкмерулі', 'Запечена курка у вершково-часниковому соусі.'], ['Poulet chkmerouli', 'Poulet rôti dans une sauce crémeuse à l’ail.'], ['Pollo shkmeruli', 'Pollo asado en salsa cremosa de ajo.'], ['Hähnchen Schkmeruli', 'Gebratenes Hähnchen in cremiger Knoblauchsauce.']],
  ['Mushroom Risotto', 'Arborio rice, porcini, parmesan.', ['Ризото з грибами', 'Рис арборіо, білі гриби й пармезан.'], ['Risotto aux cèpes', 'Riz arborio, cèpes et parmesan.'], ['Risotto de setas', 'Arroz arborio, boletus y parmesano.'], ['Pilzrisotto', 'Arborio-Reis, Steinpilze und Parmesan.']],
  ['Grilled Salmon', 'Salmon steak with seasonal vegetables.', ['Лосось на грилі', 'Стейк із лосося із сезонними овочами.'], ['Saumon grillé', 'Pavé de saumon accompagné de légumes de saison.'], ['Salmón a la parrilla', 'Lomo de salmón con verduras de temporada.'], ['Gegrillter Lachs', 'Lachssteak mit saisonalem Gemüse.']],
  ['Pelamushi', 'Traditional grape-juice pudding with walnuts.', ['Пеламуші', 'Традиційний десерт із виноградного соку з волоськими горіхами.'], ['Pélamouchi', 'Dessert traditionnel au jus de raisin et aux noix.'], ['Pelamushi', 'Postre tradicional de zumo de uva con nueces.'], ['Pelamuschi', 'Traditioneller Traubenpudding mit Walnüssen.']],
  ['Chocolate Fondant', 'Warm chocolate cake with a molten centre.', ['Шоколадний фондан', 'Теплий шоколадний кекс із рідкою серединкою.'], ['Fondant au chocolat', 'Petit gâteau au chocolat servi chaud, au cœur coulant.'], ['Coulant de chocolate', 'Bizcocho de chocolate caliente con corazón fundido.'], ['Schokoladenküchlein', 'Warmer Schokoladenkuchen mit flüssigem Kern.']],
  ['Churchkhela Cheesecake', 'Creamy cheesecake with churchkhela crumble.', ['Чизкейк із чурчхелою', 'Ніжний вершковий чизкейк із крихтою чурчхели.'], ['Cheesecake à la tchourtchkhela', 'Cheesecake crémeux garni d’éclats de tchourtchkhela.'], ['Tarta de queso con churchkhela', 'Tarta de queso cremosa con trocitos de churchkhela.'], ['Cheesecake mit Tschurtschchela', 'Cremiger Cheesecake mit Tschurtschchela-Streuseln.']],
]
const languageIndex: Record<string, number> = { uk: 2, fr: 3, es: 4, de: 5 }

export function localizedDish<T extends DishContent>(dish: T): T {
  const code = locale.value as Locale
  const translated = dish.translations?.[code]
  const seed = dishes.find(row => row[0] === dish.name)
  const pair = seed?.[languageIndex[code] ?? -1] as [string, string] | undefined
  const measures = Object.fromEntries((['weight', 'calories', 'proteins', 'fats', 'carbohydrates'] as const)
    .filter(key => dish[key] !== undefined).map(key => [key, localizedMeasure(dish[key]!)]))
  return { ...dish, ...measures,
    name: translated?.name || pair?.[0] || dish.name,
    description: translated?.description || (seed && dish.description === seed[1] ? pair?.[1] : undefined) || dish.description,
  }
}

const locations: [string, string, string, string, string][] = [
  ["Our flagship on Tbilisi's main avenue: bright hall, open kitchen and a summer terrace.", 'Наш головний ресторан на центральному проспекті Тбілісі: світла зала, відкрита кухня та літня тераса.', 'Notre restaurant phare sur l’avenue principale de Tbilissi : une salle lumineuse, une cuisine ouverte et une terrasse d’été.', 'Nuestro restaurante principal en la avenida central de Tiflis: un salón luminoso, cocina abierta y terraza de verano.', 'Unser Stammhaus an der Hauptallee von Tiflis: heller Gastraum, offene Küche und Sommerterrasse.'],
  ['A cosy neighbourhood spot in Vake with seasonal vegetarian specials.', 'Затишний ресторан у районі Ваке із сезонними вегетаріанськими стравами.', 'Une adresse chaleureuse dans le quartier de Vaké, avec des spécialités végétariennes de saison.', 'Un acogedor restaurante en el barrio de Vake con especialidades vegetarianas de temporada.', 'Ein gemütliches Restaurant im Viertel Vake mit saisonalen vegetarischen Spezialitäten.'],
  ['Old Town location with a view of the river, perfect for big company dinners.', 'Ресторан у Старому місті з видом на річку — чудове місце для вечері великою компанією.', 'Au cœur de la vieille ville, avec vue sur la rivière : le cadre idéal pour les dîners en groupe.', 'En el casco antiguo, con vistas al río: el lugar ideal para cenas en grupo.', 'In der Altstadt mit Blick auf den Fluss – ideal für gesellige Abendessen in großer Runde.'],
]
export function localizedLocation<T extends { description?: string; translations?: Translations }>(location: T): T {
  const code = locale.value as Locale
  const seed = locations.find(row => row[0] === location.description)
  return { ...location, description: location.translations?.[code]?.description || seed?.[(languageIndex[code] ?? 1) - 1] || location.description }
}

/** Only standard numeric nutrition/weight values are reformatted; custom text stays as entered. */
export function localizedMeasure(value: string): string {
  const match = /^(\d+(?:\.\d+)?)\s*(g|kg|ml|l|kcal)$/i.exec(value.trim())
  if (!match) return value
  const unit = match[2]!.toLowerCase()
  const ukrainian: Record<string, string> = { g: 'г', kg: 'кг', ml: 'мл', l: 'л', kcal: 'ккал' }
  const number = new Intl.NumberFormat(localeTag.value, { maximumFractionDigits: 6 }).format(Number(match[1]))
  return `${number} ${locale.value === 'uk' ? ukrainian[unit] : unit}`
}

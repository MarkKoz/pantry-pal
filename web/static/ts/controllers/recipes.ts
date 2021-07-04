import {Recipes} from "../models/recipes";
import {SelectedIngredients} from "../models/ingredients";
import {PaginatedModalModel} from "../models/modal";
import {Recipe} from "../models/spoonacular";

export class RecipesController {
    private _recipes: Recipes;
    private _ingredients: SelectedIngredients;
    private _modal: PaginatedModalModel<Recipe>;

    constructor(
        recipesModel: Recipes,
        ingredientsModel: SelectedIngredients,
        modalModel: PaginatedModalModel<Recipe>
    ) {
        this._recipes = recipesModel;
        this._ingredients = ingredientsModel;
        this._modal = modalModel;
    }

    public async onSearch(
        sort: string,
        cuisines: string[],
        type: string,
        maxReadyTime: string
    ): Promise<void> {
        const ingred = Array.from(this._ingredients.ingredients).join(",");
        const cuisine = cuisines.join(",");
        await this._recipes.update(ingred, sort, cuisine, type, maxReadyTime);
    }

    public onClick(recipe: Recipe) {
        if (recipe.id !== this._modal.data?.id) {
            // Go to the first page if a different recipe is opened.
            // TODO: I think ideally this should be done in the model.
            this._modal.page = 1;
        }

        this._modal.data = recipe;
    }
}

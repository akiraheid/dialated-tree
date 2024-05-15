let all = []

function addToQueue(recipe) {
	$recipe = $("<li>")
		.addClass("list-group-item")
		.attr("id", recipe.title)
		.text(recipe.title)
		.on("click", recipe, async function(e) {
			const data = e.data
			console.log(data)
			const recipe = await getRecipe(data.url)
			showRecipe(recipe)
		})

	$("#queue-ul").append($recipe)
}

async function clearQueue() {
	$("#queue-ul").empty()
}

async function getRecipe(url) {
	return $.ajax({
		url: url,
		type: "GET",
		dataType: "json",
	})
	.done(function(data) {
		return data
	})
}

function clearModal() {
	$("#modalTitle").text("")
	$("#modalBody").empty()
}

function showModal(recipe) {
	clearModal()
}

function showRecipe(recipe) {
	console.log("Got recipe")
	console.log(recipe)
	$("#title").text(recipe.title)
	$("#grocy-btn").on("click", recipe, showModal)
	$("#grocy-btn").removeClass("invisible")
	$("#source").html(`<span>From: <a href=${recipe.canonical_url}>${recipe.author}</a></span>`)

	const ingredientGroups = recipe.ingredient_groups
	let html = ""
	for(group of ingredientGroups) {
		if (group.purpose) {
			html += `<h3>${group.purpose}</h3>`
		}

		html += "<ul>"
		for(ingredient of group.ingredients) {
			html += `<li>${ingredient}</li>`
		}
		html += "</ul>"
	}
	$("#ingredients").html(html)

	const instructions = recipe.instructions_list
	html = ""
	for(item of instructions) {
		html += `<p>${item}</p>`
	}
	$("#directions").html(html)
}

async function loadAvailableRecipes() {
	console.log("Retrieving recipes")
	const data = await $.ajax({
		url: "/recipes",
		type: "GET",
		dataType: "text",
	})

	console.log("Parsing response")
	$div = $("<div>").append($.parseHTML(data))
	let lis = $div.find("li")

	// Enable the next line to test a subset of available recipes
	//lis = lis.slice(0,50) // DISABLE WHEN DONE TESTING

	$.each(lis, function(idx, li) {
		const $li = $(li)
		const $a = $($li.find("a")[0])
		const url = `/recipes/${$a.attr("href")}`
		const title = $li.text().slice(0,-5)
		item = { title: title, url: url }
		all.push(item)
		addToQueue(item)
	})

	console.log(`Found ${all.length} recipes`)
}

async function populateQueue(items) {
	console.log("Populating queue")
	for(item of items) {
		addToQueue(item)
	}
}

// keyword is already lowercase
async function keywordInRecipe(keyword, recipe) {
	if(recipe.title.toLowerCase().includes(keyword)) {
		return true
	}

	//for(ingredient of recipe.ingredients) {
	//	if(ingredient.includes(keyword)) {
	//		return true
	//	}
	//}

	return false
}

async function search() {
	clearQueue()
	let keyword = $("#searchbar").val().toLowerCase()

	console.log("Showing all recipes")
	if(!keyword) {
		populateQueue(all)
		return
	}

	console.log(`Searching for ${keyword}`)
	let i = 0
	for(item of all) {
		const match = await keywordInRecipe(keyword, item)
		if(match) {
			addToQueue(item)
			i += 1
		}
	}
	console.log(`Found ${i} recipes with keyword ${keyword}`)
}

async function handleSearchKeyPress(event) {
	if(event.key == "Enter") {
		await search()
	}
}

// TODO Load all recipe ingredients so that it's searchable
$(document).ready(async function() {
	console.log("Document ready")
	clearQueue()
	await loadAvailableRecipes()
})

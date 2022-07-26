// ----- DESTRUCTURING -----
// Destructuring assignment is a special syntax that allows us to “unpack” arrays 
// or objects into a bunch of variables, as sometimes that’s more convenient.

const turtle = {
	name: 'Bob',
	legs: 4, 
	shell: true,
	type: 'amphibious',
	meal: 10,
	diet: 'berries'
}

// Don't do this
function feed(animal){
	return `Feed ${animal.name} ${animal.meal} ${animal.diet}`;
}

// Do this
function feed ({name, meal, diet}){
	return `Feed ${name} ${meal} ${diet};`
}

// Or this
function feed(animal){
	const {name, meal, diet} = animal;
	return `Feed ${name} ${meal} ${diet};`
}

// ----- TEMPLATE LITERALS -----
// Template literals provide an easy way to interpolate variables and expressions into strings.

// Don't do this
let string = horse.name + ' is a ' + horse.size + ' horse skilled in ' + horse.skills.join(' & ');

// Do this
const {name, size, skills} = animal;
let string2 = `${name} is a ${size} horse skilled in ${skills.join(' & ')}`;


// ----- SPREAD SYNTAX -----
// The spread operator ... is used to expand or spread an iterable or an array.

 const pikachu = {name: 'Pikachu'}
 const stats = {hp: 45, attack: 60, defense: 40}
//  Supose you want to merge both objects

//  Don't do this. It is ugly and you'd better create a new immutable object.
 pikachu['hp'] = stats.hp
 pikachu['attack'] = stats.attack
 pikachu['defense'] = stats.defense
 
//  Do this
 const newPikachu = {...pikachu, ...stats}
 
//  Also possible on arrays:
 
 let pokemon = ['Arbok','Raichu','Sandshrew']
 
//  Don't do this
 pokemon.push('Bulbasaur')
 pokemon.push('Metapod')
 pokemon.push('Weedle')
 
//  Do this
 let pokemon2 = [...pokemon, 'Bulbasaur','Metapod','Weedle']


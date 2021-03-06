# communalspotify
A webapp for democratizing music in public spaces

## Contents
- [Changelog](#changelog)
- [Debug options](#debug-options)
- [Preact and javascript](#preact-and-javascript)
	- [the _defineproperty function](#_defineproperty)
- [Preact Components](#preact-components)
- [Slots](#slots)
- Tailwind
	- [Building Tailwind for dev](#building-tailwindcss-for-dev)
	- [Building Tailwind for production](#to-build-tailwind-for-production)


## Changelog
just do git commits with this template:
```
<type>(scope): <subject>
```

example:
```
fix(styles): padding on buttons

feat(templates): use base template for join.html
```

possible types are [commitizen](https://github.com/commitizen/conventional-commit-types/blob/master/index.json) standard.

![types](https://github.com/commitizen/cz-cli/raw/master/meta/screenshots/add-commit.png)

uses [git-chglog](https://github.com/git-chglog/git-chglog) to generate changelogs.


## Preact and javascript:
So, we are using [preact](https://preactjs.com) for this project, as it allows us to do fun reactivity stuff pretty easily. and is much smaller than react + react-dom.

In order to use preact, create a template with this:

```js
{%extends "preactBase.html" %}
{%block title%}title | Shareify{%endblock%}
{%block code %}

{%endblock%}
```

And you're done, you've made a template using preact!

Now to change the default contents:

`preactBase.html` has the function `Main` already declared. Those are our two components. 

Just add code that redefines the `Main` components, and preact will render that component instead of the default. 

Instead of using JSX as the html language inside our js code, we use [htm](https://github.com/developit/htm) which is quite small, and has great integration with preact. To use it, just make a tagged template literal with `html`.

```js
Main = () => (html`<p>oooh, html </p>`) 
```

> Think of template literals like python's f-strings. where instead of using `{}` to include code, you use `${}`.

**eg:**
```js
{%extends "preactBase.html" %}
{%block title%}A simple demo (clock) | Shareify{%endblock%}
{%block code %}

class Clock extends Component {

  constructor() {
	super();
	this.state = { time: Date.now() };
  }

  // Lifecycle: Called whenever our component is created
  componentDidMount() {
	// update time every second
	this.timer = setInterval(() => {
	  this.setState({ time: Date.now() });
	}, 1000);
  }

  // Lifecycle: Called just before our component will be destroyed
  componentWillUnmount() {
	// stop when not renderable
	clearInterval(this.timer);
  }

  render() {
	let time = new Date(this.state.time).toLocaleTimeString();
	return html`<span>${time}</span>`;
  }
}

main = html`<${Clock}/>`

{%endblock%}
```

This demo just displays the current time. 

**Note:**

because we are using the "module" type script tag, you have to make sure that you write correct js. That means declaring your variables, y'all. for more info about some best practices, [click here](https://github.com/airbnb/javascript). 

In regards to variables: use `const/let` instead of `var`, as `const` and `let` are block scope, whereas `var` is function-scoped (ie. global). 

### `_defineProperty()`

`_defineProperty()` is a nice little helper function to let us define properties in browsers that dont support public field declarations. This is literally just copied from a babel build. 

**How to use:**


```js
// instead of:
class Hello extends Component {
	state = {
		value:""	
	}
	
	onInput = (ev) => {
		this.setState({
			value: ev.target.value
		})
	}
	
	onSubmit = (ev) => {
		ev.preventDefault()
		
		this.setState({
			name:this.state.value
		})
	}
	
	render() {}
}

// write:
class Hello extends Component {
	constructor() {
		super()
		
		_defineProperty(this, "state", {
			value: ""
		})
		
		_defineProperty(this, "onInput", (ev) => {
			this.setState({
				value: ev.target.value
			})
		})
		
		_defineProperty(this, "onSubmit", (ev) => {
			ev.preventDefault()
			
			this.setState({
				name: this.state.value
			})
		})
	
	}

	render() {}
}

// you might also be able to write:
class Hello extends Component {
	constructor() {
		super()
		this.state = {
			value: ""
		}
		
		this.onInput = (ev) => {
			this.setState({
				value: ev.target.value
			})
		}
		
		this.onSubmit = (ev) => {
			ev.preventDefault()
		
			this.setState({
				name: this.state.value
			})
		}
	
	}
	render() {}
}

// but i need to check if that works cross-browser. Babel doesnt try to convert the above code, so, uhh, ┐(￣ヘ￣)┌,  
```

basically, from what i can tell, doing public fields as in the first example just adds them to the class using the [`defineProperty` function](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Classes/Public_class_fields#Public_static_fields). So the custom function basically just reimplements the default js behaviour, which makes sense, because it's babel.

## Preact Components:
all components live inside the `components` directory, under individual js files. 

for information on how to make them, [have a look here](https://preactjs.com/guide/v10/components)

to import a component, add this to the top of the `code` block:

```
{{component_import("Spacer", "WhateverTheFileNameIs", ...)}}
```

The component name in js should be the same as the filename excluding the extension, not because it affects anything, just because it's nicer.

Then to use a component, include the component like this in your htm template:
```jsx
html`
	<${TheNameOfYourComponent> <//>
`
// or self-closing:
html`
	<${TheNameOfYourComponent />
`
```


### A list of our components:

| name | props | description |
|------|-------|-------------|
| `Spacer` | `{text: string}` | takes `text` and puts it in between two lines. adds y padding. If it can't find `text`, just displays a line. |
| `DefaultHeader` | `{}` | Shows the header/navbar thingo. |
| `Link` | `{text: string, href: string, hoverColors: array}` | shows an `a` tag with innerHTML = text, href = href, and hover styling done by hoverColors. hoverColors is set by default to the yellow and black hightlight. |

**Note**: some components require other components to be loaded, make sure that you load them in your template. `Header` and `Link` are imported by default.

## Slots
in order to have the components talk to other parts without having to pass down props, we can use slots.

basically a slot is an element that has some default content, that can then be overwritten by another element somewhere else.

```jsx

<${Slot} name="foo">
    Fallback content
<//>
<${SlotContent} name="foo">
    content to replace the other one with.
<//>

```

Those two elements dont have to be in the same level or anything, they talk to each other using the context api, but you don't need to know how that works.

The header component's nav elements are included in the slot `"headerNav"`. this is so you can basically change the contents of it to like, show the room code there.

## Building tailwindcss for dev:
just run `npm i` inside this folder, and it'll install the required packages.

And then run
```bash
$ npm run tcss:dev
```

## To build tailwind for production:
basically, the dev version of tailwind is pretty massive (2.26MB), but usually you don't need all of the classes provided to you by tailwind. So we have to purge the css of unused classes. 

To do this, run
```bash
$ npm run tcss:prod
```

> note: i've only tested this with bash. If you have problems with the npm script, basically just run `npm run tcss:dev` with the `NODE_ENV` environmental variable set to `production`. (although, i am using cross-env, so it should work)

PurgeCSS will look for tailwindcss classes in both `.html` and `.js` files inside of the `./templates` dir. And will look in `.js` files inside `./components`. [**Don't use string concatenation to create class names. Instead dynamically select a complete class name**](https://tailwindcss.com/docs/controlling-file-size#writing-purgeable-html)

You shouldn't ever build tailwind for production on your machine. It should be built into the production version when being uploaded to the server. (so, you can run `tcss:prod` as a build step basically)


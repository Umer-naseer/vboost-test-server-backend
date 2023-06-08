/*
	Vboost widget
	ver. 1.04
	07/07/2017
*/
"use strict";

(function() {
	const ver = '1.05';
	//const debug = true;

	const companyID = {{ company.id }};
	const companyName = "{{ company.name }}";

	const widgetHost = '';
	const coverImage = {% if cover_image.image.image %}"{{ widget_host }}/media/{{ cover_image.image.image }}"{% else %}null{% endif %};

	const scriptMask = "script[src='{{ widget_script }}']";
	const staticPath = (typeof debug == 'undefined') ? "{{ static_path }}" : "http://localhost/rm/home/vboost/vbo/live/static/live/widget/";
	const staticSuffix = "?" + ver;
	const jQueryPath = "https://ajax.googleapis.com/ajax/libs/jquery/1.12.4/jquery.min.js"

	const widgetApiRootUrl = (typeof debug == 'undefined') ? "" : 'http://vboostoffice.criterion-dev.net/api/v1/live/';
	const packagesAPI = '{{ widget_api_root_url }}packages/';
	const montageAPI = '{{ widget_api_root_url }}montage/';

	const pageLimit = 12;

	let curPage, overlayDiv, innerDiv;

	function pButton(symbol, display, toPage) { // display pagination button
		if (display == false) return '';
		if (toPage != false) return ' <span class="link" data-to="' + toPage  + '">' + symbol + '</span>';
		return '<span class="' + ((symbol == '…') ? 'ellipsis' : 'regular') + '">' + symbol + '</span>';
	}

	function disableOverlay() {
		overlayDiv.hide();
		innerDiv.css('opacity', 1);
	}

	const monthNames = [
		"January", "February", "March", "April",
		"May", "June", "July", "August",
		"September", "October", "November", "December"
	];

	const monthNamesShort = [
		"Jan", "Feb", "Mar", "Apr", "May", "Jun",
		"Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
	];

	function formatUTCTime(time) {
		time = new Date(time);
		let hours = time.getHours();
		let pm = (hours >= 12);
		hours %= 12;
		if (hours == 0) hours = 12;
		return (monthNames[time.getMonth()] + ' ' + time.getDate() + ', '
			+ time.getFullYear() + ', ' + hours + ':'
			+ (time.getMinutes()<10?'0':'') + time.getMinutes() + ' ' + (pm ? 'p.m.' : 'a.m.'));
	}

	function loadSidebar() { // get sidebar data from API
		$.ajax({
			url: montageAPI + companyID + "/",
			type: "GET",
			crossDomain: true,
			success: function(data) {
				let html = '';

				for (var i in data) {
					if (!data[i].image) continue;

					let d = data[i].date.split('-');
					if (d.length == 3)
						data[i].date = monthNamesShort[parseInt(d[1]) - 1]
							+ '. ' + d[2] + ', ' + d[0];

					html +=
						'<a href="' + data[i].video + '" target="_blank">'
						  + '<img src="' + widgetHost + data[i].image + '">'
						  + '<span class="date">' + data[i].date + '</span>'
						  + ((i > 0) ? '' : '<span class="monthly">Monthly slide show</span>')
						  + '<span class="name">' + companyName + '</span>'
						  + '<br>'
					  + '</a>';
				}
				$('div.VboostWidget div.dynamicSidebar').html(html);
			},
			error: function(){
				alert('AJAX error geting data from montage API.');
			}
		});
	}

	function goToPage(ptr) { // CSS and jQuery are loaded
		curPage = ptr;

		overlayDiv.show();
		innerDiv.css('opacity', 0.5);

 		// prepare API parameters
		let url = packagesAPI + companyID + "/"
			+ "?limit=" + pageLimit
			+ "&offset=" + ((curPage - 1) * pageLimit);

		// get data from API
		$.ajax({
			url: url,
			type: "GET",
			crossDomain: true,
			success: function(data) {

				let count = data.count || 0;
				let results = data.results || [];
				let html = '';

				for (var i in results) {
					let res = results[i];

					// ISO => March 14, 2017, 4:58 p.m.
					let time = formatUTCTime(res.last_mailed);

					html +=
						  '<a class="cell" href="' + res.url + '" target="_blank">'
							+ '<img src="' + widgetHost + res.image + '">'
							+ '<div class="date">' + time + '</div>'
							+ '<h2>Ask for: <span class="rep">' + res.contact + '</span>'
							+ '</h2>'
						+ '</a>';
				}

				if (count) {

					// pagination
					let lastPage = parseInt((count + pageLimit - 1) / pageLimit);

					if (curPage > lastPage) curPage = lastPage;
					if (curPage < 1) curPage = 1;

					html += '<div class="pagination">'

					html += pButton('&lt;', (curPage > 2), curPage - 1); // previuos '<'
					html += pButton(1, (curPage > 1), (curPage > 1) ? 1 : false); // first
					html += pButton('…', (curPage > 3), false); // ellipsis

					html += pButton(curPage - 1, (curPage > 2), curPage - 1); // before current
					html += pButton(curPage, true, false); // current
					html += pButton(curPage + 1, (curPage < lastPage - 1), curPage + 1); // after current

					html += pButton('…', (curPage < lastPage - 2), false); // ellipsis
					html += pButton(lastPage, (curPage != lastPage), (curPage != lastPage) ? lastPage : false); // last
					html += pButton('&gt;', (curPage < lastPage - 1), curPage + 1); // next '>'

					html += '</div>';
				}

				// update data
				$('div.VboostWidget div.cellContainer').html(html);
				disableOverlay();

				// bink click
				let pagDiv = innerDiv.find('div.pagination');
				pagDiv.find('span.link').click(function(e){
					pagDiv.find('span.regular').removeClass('regular').addClass('ellipsis');
					e = $(e.target);
					e.removeClass('link').addClass('regular');

					$('html, body').animate({scrollTop:0}, 'slow');

					goToPage(e.data('to'));
				});
			},
			error: function(){
				disableOverlay();
				alert('AJAX error geting data from packages API.');
			}
		});
	}

	function startWidget() { // CSS and jQuery are loaded

		// jQuery is ready now
		$.noConflict = true;

		let script = $(scriptMask);
		if (!script.length) {
			alert('Cannot find script by mask.');
			return;
		}

		// create main <div> after self <script>
		// note: more than 1 script may be included
		script.eq(0).after(
			$('<div class="VboostWidget"></div>')
				.append(overlayDiv = $(
					'<div class="vboostWidgetOverlay">' +
						'<span></span>' +
					'</div>'
				))
				.append(innerDiv = $(
					'<div class="vboostWidgetInner">' +
						'<div class="rightColumn">' +
							'<div class="fiveStar">RECENT SLIDE SHOW</div>' +
							'<div class="dynamicSidebar"></div>' +
						'</div>' +
						'<div class="leftColumn">' +
							(coverImage ? '<img src="' + coverImage + '" title="' + companyName + '" class="coverImage">' : '') +
							'<h1>' + companyName + '</h1>' +
							'<h3>RECENT PHOTOS</h3>' +
							'<div class="cellContainer"></div>' +
						'</div>' +
						'<br>',
					'</div>'
				))
				.append('<div class="vboostWidgetClear"></div>')
		);

		// start at 1st page
		goToPage(1);

		// async fill sidebar once
		loadSidebar();

		$(window).resize(responseOnWidth);
		setTimeout(responseOnWidth, 100);
	};

	// set base class depends on width
	let curInnerClass;
	function responseOnWidth() {
		let w = $('div.VboostWidget div.vboostWidgetClear').width();

		let newClass = (w >= 1128) ? 's4' :
			((w >= 900) ? 's3' :
				((w >= 700)) ? 's2' : 's1');

		if (curInnerClass != newClass)
			innerDiv
				.removeClass(curInnerClass)
				.addClass(curInnerClass = newClass);
	}

	if (document.VboostWidgetLoaded !== undefined)
		return; // do not allow to run the script twice
	document.VboostWidgetLoaded = true;

	let cssLoaded = false, jqueryLoaded = false;

	// loading CSS
	let css = document.createElement('link');
	css.rel = 'stylesheet';
	css.type = 'text/css';
	css.onload = function(){
		cssLoaded = true;
		if (jqueryLoaded) startWidget();
	}
	css.href = staticPath + 'widget.css' + staticSuffix;
	document.getElementsByTagName('head')[0].appendChild(css);

	// loading jQuery
	let jquery = document.createElement("script");
	jquery.src = jQueryPath;
	jquery.onload = function(){
		jqueryLoaded = true;
		if (cssLoaded) startWidget();
	};
	jquery.onerror = function(){
		alert('Error loading jQuery .');
	};
	document.body.appendChild(jquery);

}).call(window.vboostLiveWidget = window.vboostLiveWidget || {});

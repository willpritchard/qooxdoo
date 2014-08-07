"use strict";
/* ************************************************************************

   qooxdoo - the new era of web development

   http://qooxdoo.org

   Copyright:
     2004-2012 1&1 Internet AG, Germany, http://www.1und1.de

   License:
     LGPL: http://www.gnu.org/licenses/lgpl.html
     EPL: http://www.eclipse.org/org/documents/epl-v10.php
     See the LICENSE file in the project's top-level directory for details.

   Authors:
     * Christopher Zuendorf (czuendorf)

************************************************************************ */


/**
 * Creates a HTML canvas widget in your mobile application.
 *
 * *Example*
 *
 * Here is an example of how to use the canvas widget.
 *
 * <pre class='javascript'>
 * var canvas = new qx.ui.mobile.embed.Canvas();
 *
 * canvas.setWidth(150);
 * canvas.setHeight(150);
 * this.getContent().add(canvas);
 *
 * var ctx = canvas.getContext2d();
 * ctx.strokeStyle = '#3D72C9';
 * ctx.beginPath();
 * ctx.arc(75,85,50,0,Math.PI*2,true);
 * ctx.moveTo(110,85);
 * ctx.arc(75,85,35,0,Math.PI,false);
 * ctx.moveTo(65,75);
 * ctx.arc(60,75,5,0,Math.PI*2,true);
 * ctx.moveTo(95,75);
 * ctx.arc(90,75,5,0,Math.PI*2,true);
 * ctx.stroke();
 * </pre>
 *
 */
qx.Bootstrap.define("qx.ui.mobile.embed.Canvas",
{
  extend : qx.ui.mobile.core.Widget,


  members :
  {
    // overridden
    _getTagName : function()
    {
      return "canvas";
    },


    /**
     * Get the canvas element [<a href="http://www.whatwg.org/specs/web-apps/current-work/multipage/the-canvas-element.html#canvas">W3C-HMTL5</a>]
     *
     * @return {Element} The canvas DOM element.
     */
    getCanvas : function() {
      return this[0];
    },


    /**
     * Set the width attribute of the canvas element. This property controls the
     * size of the canvas coordinate space.
     *
     * @param width {Integer} canvas width
     */
    setWidth : function(width) {
      this[0].width = width;
    },


    /**
     * Get the width attribute of the canvas element
     *
     * @return {Integer} canvas width
     */
    getWidth : function() {
      return this[0].width;
    },


    /**
     * Set the height attribute of the canvas element. This property controls the
     * size of the canvas coordinate space.
     *
     * @param height {Integer} canvas height
     */
    setHeight : function(height) {
      this[0].height = height;
    },


    /**
     * Get the height attribute of the canvas element
     *
     * @return {Integer} canvas height
     */
    getHeight : function() {
      return this[0].height;
    },


    /**
     * Get the canvas' 2D rendering context
     * [<a href="http://www.whatwg.org/specs/web-apps/current-work/multipage/the-canvas-element.html#canvasrenderingcontext2d">W3C-HTML5</a>].
     * All drawing operations are performed on this context.
     *
     * @return {CanvasRenderingContext2D} The 2D rendering context.
     */
    getContext2d : function() {
      return this[0].getContext("2d");
    }
  }
});

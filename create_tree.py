from PIL import Image, ImageDraw

def create_placeholder():
    img = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Simple triangle tree
    d.polygon([(256, 50), (100, 450), (412, 450)], fill=(34, 139, 34), outline=(0,0,0))
    img.save('assets/tree.png')
    print("Created placeholder tree.png")

if __name__ == "__main__":
    create_placeholder()
